"""Finite logic reader: declarations and named rules, without evaluation.

The reader produces the same immutable declaration nodes as the legacy data
reader. Semantic elaboration remains a native Shen responsibility.
"""
from __future__ import annotations
import json
import re
from .parser import Location, Node, Symbol, SpecError

_TOKEN = re.compile(r'\s+|//[^\n]*|"(?:[^"\\]|\\.)*"|:-|::|->|!=|<=|>=|[A-Za-z_$][A-Za-z_0-9$-]*|-?[0-9]+|[.,:()!<>={}]')
# ``$`` and braces are lexed everywhere but accepted only inside a
# ``.template`` body (see templates.py); elsewhere they are syntax errors.
_TEMPLATE_IDENTIFIER = re.compile(r'[A-Za-z_$][A-Za-z_0-9$-]*')


def _node(value, loc):
    if isinstance(value, dict):
        return Node((Node(Symbol('object'), loc), *(Node((Node(Symbol(k), loc), _node(v, loc)), loc) for k,v in value.items())), loc)
    if isinstance(value, list):
        return Node((Node(Symbol('array'), loc), *(_node(v, loc) for v in value)), loc)
    return Node(value, loc)


def parse_logic(text, source):
    if len(text.encode('utf-8')) > 16 * 1024 * 1024:
        raise SpecError('source exceeds 16 MiB', code='spec-resource')
    tokens = []
    offset, line, column = 0, 1, 1
    for match in _TOKEN.finditer(text):
        if match.start() != offset:
            raise SpecError('unsupported logic syntax', Location(source, line, column, offset))
        token = match.group()
        if not token.isspace() and not token.startswith('//'):
            tokens.append((token, Location(source,line,column,offset)))
        newlines = token.count('\n')
        column = len(token.rsplit('\n',1)[-1])+1 if newlines else column+len(token)
        line += newlines
        offset = match.end()
    if offset != len(text):
        raise SpecError('unterminated token', Location(source,text.count('\n',0,offset)+1,1,offset))
    pos, anonymous = 0, 0
    out = []
    in_template = False

    def peek():
        return tokens[pos][0] if pos < len(tokens) else ''

    def take(expected=None):
        nonlocal pos
        if pos == len(tokens):
            raise SpecError(f'expected {expected or "token"}, found end of source')
        token, loc = tokens[pos]
        if expected is not None and token != expected:
            raise SpecError(f'expected {expected}, found {token}', loc)
        pos += 1
        return token

    def name():
        value = take()
        if '$' in value:
            if not in_template:
                raise SpecError('template parameter outside a .template body',tokens[pos-1][1],'template-syntax')
            if not _TEMPLATE_IDENTIFIER.fullmatch(value):
                raise SpecError('expected identifier',tokens[pos-1][1])
            return value
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9-]*', value):
            raise SpecError('expected identifier',tokens[pos-1][1])
        return value

    def string():
        value = take()
        if not value.startswith('"'):
            raise SpecError('expected quoted string',tokens[pos-1][1])
        return json.loads(value)

    def names():
        take('('); result=[]
        if peek() != ')':
            result.append(name())
            while peek() == ',':
                take(','); result.append(name())
        take(')'); return result

    def emit(tag, value, loc):
        out.append(Node((Node(Symbol(tag),loc),_node(value,loc)),loc))

    def term():
        nonlocal anonymous
        value=take()
        if value.startswith('"') or re.fullmatch('-?[0-9]+',value) or value in ('true','false'):
            literal=json.loads(value)
            typ='boolean' if isinstance(literal,bool) else 'symbol' if isinstance(literal,str) else 'unsigned'
            if peek() == '::':
                take('::'); typ=name()
            return dict(value=literal,type=typ)
        if value.startswith('$'):
            if not in_template:
                raise SpecError('template parameter outside a .template body',tokens[pos-1][1],'template-syntax')
            if not re.fullmatch('[$][A-Z][A-Za-z0-9]*', value):
                raise SpecError('a parameter term is exactly $Name',tokens[pos-1][1],'template-syntax')
            typ='symbol'
            if peek() == '::':
                take('::'); typ=name()
            return dict(parameter=value[1:],type=typ)
        if not re.fullmatch('[A-Z_][A-Za-z_0-9]*', value):
            raise SpecError('variables start with an uppercase letter; constants are quoted',tokens[pos-1][1])
        if value.startswith('__spec_anon_'):
            raise SpecError('reserved anonymous variable prefix',tokens[pos-1][1])
        if value == '_':
            anonymous+=1; value=f'__spec_anon_{anonymous}'
        return dict(name=value)

    def atom():
        neg=peek()=='!'
        if neg: take('!')
        rel=name(); take('('); terms=[]
        if peek()!=')':
            terms.append(term())
            while peek()==',': take(','); terms.append(term())
        take(')')
        return dict(relation=rel,terms=terms,negated=neg)

    def rule_value():
        rule=name(); take(':'); head=atom(); take(':-'); body=[]
        while True:
            if peek() == '!' or (pos+1<len(tokens) and tokens[pos+1][0]=='('):
                body.append(atom())
            else:
                left=term(); op=take()
                if op not in ('=','!=','<','<=','>','>='):
                    raise SpecError('unsupported comparison', tokens[pos-1][1])
                body.append(dict(left=left,operator=op,right=term()))
            if peek()!=',': break
            take(',')
        take('.')
        return dict(name=rule,head=head,body=body)

    def template_node(loc):
        """``.template name(P, ...) { rule ... }``: rules only, never nested.

        The node carries the header and the unexpanded rule nodes, each with
        its own location; expansion is ``templates.expand_templates``."""
        nonlocal in_template
        identity=name(); parameters=names(); take('{')
        in_template=True
        rules=[]
        while peek() != '}':
            if not peek():
                raise SpecError('unterminated .template body',loc,'template-syntax')
            if peek() == '.':
                raise SpecError('a .template body contains rules only',tokens[pos][1],'template-syntax')
            rule_loc=tokens[pos][1]
            rules.append(Node((Node(Symbol('rule'),rule_loc),_node(rule_value(),rule_loc)),rule_loc))
        take('}')
        in_template=False
        header=_node(dict(name=identity,parameters=parameters),loc)
        return Node((Node(Symbol('template'),loc),header,*rules),loc)

    take('.'); take('claims'); take('2'); take('.')
    while peek():
        loc=tokens[pos][1]
        if peek() != '.':
            emit('rule',rule_value(),loc)
            continue
        take('.'); tag=name()
        if tag=='template':
            out.append(template_node(loc))
        elif tag=='instantiate':
            template=name(); arguments=names(); take('.')
            emit('instantiate',dict(template=template,arguments=arguments),loc)
        elif tag=='import':
            path=string(); take('.')
            out.append(Node((Node(Symbol('import'),loc),Node(path,loc)),loc))
        elif tag=='pack':
            value=dict(id=string()); take('schema'); value['schema_version']=int(take())
            while peek()!='.':
                key=name()
                if key not in ('description','primitives_source'): raise SpecError('unknown pack field',loc)
                value[key]=string()
            take('.'); emit('pack',value,loc)
        elif tag=='decl':
            rel=name(); take('('); cols=[]
            while peek()!=')':
                col=name(); take(':'); typ=name(); ctx=peek()=='ctx'
                if ctx: take('ctx')
                cols.append(dict(name=col,type=typ,context=ctx))
                if peek()!=',': break
                take(',')
            take(')'); section=name(); modality=name(); binding=name()
            if section not in ('primitive','supplementary-primitive','derived'): raise SpecError('unknown declaration class',loc)
            value=dict(name=rel,columns=cols,primitive=section!='derived',modality=modality,binding=binding,
                       context_indices=[c['name'] for c in cols if c['context']],polarity='positive',
                       finite=False,nonempty=False,completes=None,producer_classes=[],compatibility_targets=[],compatibility_context_indices=[])
            while peek()!='.':
                key=name()
                if key in ('finite','nonempty'): value[key]=True
                elif key=='negative': value['polarity']='negative'
                elif key=='completes': value['completes']=name()
                elif key in ('producers','legacy_targets','legacy_context'):
                    value[dict(producers='producer_classes',legacy_targets='compatibility_targets',legacy_context='compatibility_context_indices')[key]]=names()
                else: raise SpecError(f'unsupported declaration attribute {key}',loc)
            take('.'); emit(section,value,loc)
        elif tag=='completes':
            closure=name(); take('->'); target=name(); take('by'); mapping=[]
            while True:
                left=name(); take('='); right=name(); mapping.append([left,right])
                if peek()!=',': break
                take(',')
            take('.'); emit('completeness-scope',dict(relation=closure,target=target,mapping=mapping),loc)
        elif tag=='capability':
            identity=name(); take('witness'); witness=name()
            left=name(); take(':'); ld=name(); take('->'); right=name(); take(':'); rd=name()
            take('left'); lt=names(); take('right'); rt=names()
            sym=peek()=='symmetric'
            if sym: take('symmetric')
            take('.'); emit('capability',dict(name=identity,witness=witness,left_column=left,right_column=right,
                left_dimension=ld,right_dimension=rd,left_targets=lt,right_targets=rt,symmetric=sym),loc)
        elif tag=='bridge':
            identity=name(); ld=name(); take('->'); rd=name(); take('.')
            emit('required-bridge',dict(name=identity,left_dimension=ld,right_dimension=rd),loc)
        elif tag=='policy':
            identity=name(); take('rule'); rule=name(); take('completes'); rel=name(); take('digest'); sha=string(); take('.')
            emit('derived-completeness-policy',dict(name=identity,rule=rule,relation=rel,rule_digest=sha),loc)
        else:
            raise SpecError(f'unsupported logic declaration {tag}',loc)
    return tuple(out)
