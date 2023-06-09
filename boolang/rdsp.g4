grammar rdsp;

program
    : block EOF
    ;

block
    : (stat ';'?)* laststat?
    ;

stat
    : nametype '=' exp // nowa zmienna
    | var '=' exp // przypisanie
    | functioncall
    | 'do' block 'end'
    | 'while' exp 'do' block 'end'
    | 'if' exp 'then' block ('elseif' exp 'then' block)* ('else' block)? 'end'
    | 'for' NAME '=' exp ',' exp (',' exp)? 'do' block 'end' // over an integer range
    | 'for' NAME ',' NAME 'in' functioncall 'do' block 'end' // where functioncall is an iterator like pairs
    | 'function' NAME functionbody
    ;

var
    : NAME suffix?
    ;

nametype
    : NAME ':' type
    ;

type
    : NAME
    | listType
    | unionType
    | tableType
    ;

tableType // type in square brackets defines type under integer keys
    : 'Table' '[' type ']'
    ;

unionType
    : 'Union' '[' type (',' type)+ ']'
    ;

listType
    : 'List' '[' type ']'
    ;

prefix
    : var
    | functioncall suffix?
    ;

suffix
    : ('[' exp ']' | '.' NAME)+
    ;

exp
    : number
    | string
    | TRUE
    | FALSE
    | 'nil'
    | prefix
    | exp binop exp
    | unop exp
    | tableconstructor
    ;

functionbody
    : '(' typednamelist? ')' '->' type block 'end'
    ;

laststat
    : ('return' explist? | 'break' | 'continue') ';'?
    ;

typednamelist
    : nametype (',' nametype)*
    ;

functioncall
    : NAME '(' explist? ')'
    ;

explist
    : exp (',' exp)*
    ;

tableconstructor
    : '{' fieldlist? '}'
    ;

fieldlist
    : field (',' field)*
    ;

field
    : '[' exp ']' ':' type '=' exp
    | nametype '=' exp // foo: string = "bar" === ["foo"]: string = "bar"
    | exp // integer keys
    ;

binop
    : '+'
    | '-'
    | '*'
    | '/'
    | '%'
    | '^'
    | '#'
    | '=='
    | '~='
    | '<='
    | '>='
    | '<'
    | '>'
    | '|'
    | '&'
    | 'or'
    | 'and'
    | '..' // string concatenation
    ;

unop
    : '-'
    | 'not'
    | '#'
    ;

string
    : (DOUBLEQUOTESTRING | SINGLEQUOTESTRING) ('..' string)?
    ;

number
    : INT
    | FLOAT
    ;

NAME
    : [a-zA-Z_][a-zA-Z_0-9]*
    ;


FALSE
    : 'false'
    ;

TRUE
    : 'true'
    ;

INT
    : '0'
    | [1-9] Digit*
    ;

FLOAT
    : Digit+ '.' Digit*
    | '.' Digit+
    ;

DOUBLEQUOTESTRING
    : '"' ( EscapeSequence | ~('\\'|'"') )* '"'
    ;

SINGLEQUOTESTRING
    : '\'' ( EscapeSequence | ~('\''|'\\') )* '\''
    ;

fragment Digit
    : [0-9]
    ;

fragment EscapeSequence
    : '\\' [abfnrtvz"'|\\]
    | '\\' '\r'? '\n'
    ;

WHITESPACE
    : [ \t\u000C\r\n]+ -> skip
    ;
