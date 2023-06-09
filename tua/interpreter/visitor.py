from .generated.TuaVisitor import TuaVisitor
from .generated.TuaParser import TuaParser
from .log import log
from .scope import ScopeStack
from .tualist import TuaList
from .variables import Value, Type, Function, Param
from .errors import SemanticError, InternalError

class Tua(TuaVisitor):
    def __init__(self):
        self.scope: ScopeStack = ScopeStack()
        from . import builtins
        self.builtins = {
            "print": builtins.print_,
            "type": builtins.type_,
            "len": builtins.len_,
            "concat": builtins.concat_,
            "append": builtins.append_,
            "pop": builtins.pop_,
            "ipairs": builtins.ipairs_,
            "dump_stack": builtins.dump_stack,
        }
        self.cnt = 0 # for temporary testing
        self.depth = 0

    def visitProgram(self, ctx:TuaParser.ProgramContext):
        log.info("Program")
        return self.visitChildren(ctx)


    def visitBlock(self, ctx:TuaParser.BlockContext):
        log.info("Block")
        self.scope.push()
        self.depth += 1

        for c in ctx.getChildren():
            results = self.visit(c)
            if results is not None:

                self.depth -= 1
                if self.depth > 0: # necessary for line by line execution
                    self.scope.pop()
                return results

        self.depth -= 1
        if self.depth > 0: # necessary for line by line execution
            self.scope.pop()
        return None



    def visitStat(self, ctx:TuaParser.StatContext):
        if not ctx.functioncall():
            return self.visitChildren(ctx)

        self.visitChildren(ctx)

    def visitNewvariable(self, ctx:TuaParser.NewvariableContext):
        log.info("Newvariable")
        lhs: Value
        type_annotated: Type
        lhs, type_annotated = self.visit(ctx.nametype())
        rhs: Value = self.visit(ctx.exp())
        if rhs.type.id != type_annotated.id:
            if rhs.type.id == "List[]":
                rhs.type.id = type_annotated.id
                rhs.value.type = type_annotated.id[5:-1]
            else:
                raise SemanticError(f"Type mismatch: ({rhs.type.id}) ({type_annotated.id})")

        var_added_successfully = self.scope.new_identifier(lhs, rhs)

        if not var_added_successfully:
            raise SemanticError(f"Variable named '{lhs}' is already defined")

    def visitAssignment(self, ctx:TuaParser.AssignmentContext):
        log.info("Assignment")
        identifier, suffix = self.visit(ctx.var())
        value = self.visit(ctx.exp())
        if suffix is None:
            self.scope.change_value(identifier, value)
        else:
            self.scope.change_value_with_suffix(identifier, value, suffix)

    def visitVar(self, ctx:TuaParser.VarContext) -> tuple[str, any]:
        log.info("Var")
        name = ctx.getToken(TuaParser.NAME, 0).getText()
        if ctx.suffix():
            suffix = self.visit(ctx.suffix())
            return name, suffix
        return name, None


    def visitNametype(self, ctx:TuaParser.NametypeContext) -> tuple[str, Type]:
        log.info("Nametype")
        name = ctx.NAME().getText()
        type = self.visit(ctx.type_())
        return (name, type)


    def visitType(self, ctx:TuaParser.TypeContext) -> Type:
        log.info("Type")
        if ctx.NAME():
            return Type(ctx.NAME().getText())
        elif ctx.NIL():
            return Type("nil")
        elif ctx.listType():
            return self.visit(ctx.listType())
        elif ctx.unionType():
            raise NotImplementedError
        elif ctx.tableType():
            raise NotImplementedError
        else:
            raise InternalError


    def visitTableType(self, ctx:TuaParser.TableTypeContext):
        log.info("TableType")
        return self.visitChildren(ctx)


    def visitUnionType(self, ctx:TuaParser.UnionTypeContext):
        log.info("UnionType")
        return self.visitChildren(ctx)


    def visitListType(self, ctx:TuaParser.ListTypeContext) -> Type:
        log.info("ListType")
        elem_type: Type = self.visit(ctx.type_())
        return Type(f"List[{elem_type.id}]")


    def visitPrefix(self, ctx:TuaParser.PrefixContext) -> Value:
        log.info("Prefix")
        if ctx.var():
            identifier, suffix = self.visit(ctx.var())
            ret = self.scope.get(identifier)

            if ret is None:
                raise SemanticError(f"Name '{identifier}' is not defined")

            if suffix is not None :
                if suffix < ret.value.length() and suffix >= 0:
                    return ret.value.get(suffix)
                else:
                    raise SemanticError(f"Index out of range: {suffix} for {identifier}")
            else:
                return ret
        elif ctx.functioncall():
            return self.visit(ctx.functioncall())
        else:
            return NotImplementedError


    def visitSuffix(self, ctx:TuaParser.SuffixContext):
        log.info("Suffix")
        if ctx.exp():
            arg: Value = self.visit(ctx.exp(0))
            return arg.value
        return self.visitChildren(ctx)


    def visitExp(self, ctx:TuaParser.ExpContext) -> Value:
        log.info("Exp")
        if ctx.parexp():
            return self.visit(ctx.parexp())
        elif ctx.number():
            value, type = self.visit(ctx.number())
            assert isinstance(type, Type)
            assert isinstance(type.id, str)

            return Value(type, value)
        elif ctx.string():
            return self.visit(ctx.string())
        elif ctx.bool_():
            value, type = self.visit(ctx.bool_())
            return Value(type, value)
        elif ctx.NIL():
            return Value(Type("nil"), None)
        elif ctx.prefix():
            return self.visit(ctx.prefix())

        elif ctx.binopPower():
            base = self.visit(ctx.exp(0))
            exp = self.visit(ctx.exp(1))

            # check if the values are numbers
            if base.type.id in ("int", "float") and exp.type.id in ("int", "float"):
                result = pow(base.value, exp.value)
                type_ = Type("int") if isinstance(result, int) else Type("float")

                return Value(type_, result)

            raise SemanticError(f"Trying to use operator '^' on {base.type} and {exp.type}")

        elif ctx.unop():
            operators = {
                '-' : lambda x : -x,
                'not' : lambda x: not x
            }

            value = self.visit(ctx.exp(0))
            op = self.visit(ctx.unop())

            # check if the correct operator was used on given type

            is_strict_num = isinstance(value.value, (int, float)) and not isinstance(value.value, bool)

            if (op == '-' and is_strict_num) or (op == 'not' and isinstance(value.value, bool)):
                return Value(value.type, operators[op](value.value))

            raise SemanticError(f"Trying to use operator '{op}' on {value.type}")

        elif ctx.binopMulDivMod():
            operators = {
                '*' : lambda x, y : x * y,
                '/' : lambda x, y : x / y,
                '%' : lambda x, y : x % y,
                '//' : lambda x, y : x // y
            }

            val_left = self.visit(ctx.exp(0))
            val_right = self.visit(ctx.exp(1))

            op = self.visit(ctx.binopMulDivMod())

            # check if the values are numbers
            if val_left.type.id in ("int", "float") and val_right.type.id in ("int", "float"):
                result = operators[op](val_left.value, val_right.value)
                type_ = Type("int") if isinstance(result, int) else Type("float")

                return Value(type_, result)

            raise SemanticError(f"Trying to use operator '{op}' on {val_left.type} and {val_right.type}")

        elif ctx.binopAddSub():
            operators = {
                '+' : lambda x, y : x + y,
                '-' : lambda x, y : x - y,
            }

            val_left = self.visit(ctx.exp(0))
            val_right = self.visit(ctx.exp(1))

            op = self.visit(ctx.binopAddSub())

            # check if the values are numbers
            if val_left.type.id in ("int", "float") and val_right.type.id in ("int", "float"):
                result = operators[op](val_left.value, val_right.value)
                type_ = Type("int") if isinstance(result, int) else Type("float")

                return Value(type_, result)

            raise SemanticError(f"Trying to use operator '{op}' on {val_left.type} and {val_right.type}")

        elif ctx.binopConcat():
            val_left = self.visit(ctx.exp(0))
            val_right = self.visit(ctx.exp(1))

            if val_left.type.id == "string" and val_right.type.id == "string":
                return Value(Type("string"), val_left.value + val_right.value)

            raise SemanticError(f"Trying to use operator '..' on {val_left.type} and {val_right.type}")


        elif ctx.binopComparison():
            operators = {
                '==' : lambda x, y : x == y,
                '~=' : lambda x, y : x != y,
                '<=' : lambda x, y : x <= y,
                '>=' : lambda x, y : x >= y,
                '<' : lambda x, y : x < y,
                '>' : lambda x, y : x > y,
            }

            val_left = self.visit(ctx.exp(0))
            val_right = self.visit(ctx.exp(1))

            op = self.visit(ctx.binopComparison())

            # check if the correct operator was used on given types
            if (op in ('==', '~=') and val_left.type.id == val_right.type.id) or (op in ('<=', '>=', '<', '>') and val_left.type.id in ("int", "float", "string") and val_left.type.id == val_right.type.id):
                return Value(Type("bool"), operators[op](val_left.value, val_right.value))

            raise SemanticError(f"Trying to use operator '{op}' on {val_left.type} and {val_right.type}")

        elif ctx.binopAnd():
            operators = {
                'and' : lambda x, y : x and y,
                '&' : lambda x, y : x & y,
            }

            val_left = self.visit(ctx.exp(0))
            val_right = self.visit(ctx.exp(1))
            op = self.visit(ctx.binopAnd())

            # check if the correct operator was used on given types
            if val_left.type.id == "bool" and val_right.type.id == "bool":
                return Value(Type("bool"), operators[op](val_left.value, val_right.value))

            raise SemanticError(f"Trying to use operator '{op}' on {val_left.type} and {val_right.type}")

        elif ctx.binopOr():
            operators = {
                'or' : lambda x, y : x or y,
                '|' : lambda x, y : x | y,
            }

            val_left = self.visit(ctx.exp(0))
            val_right = self.visit(ctx.exp(1))
            op = self.visit(ctx.binopOr())

            # check if the correct operator was used on given types
            if val_left.type.id == "bool" and val_right.type.id == "bool":
                return Value(Type("bool"), operators[op](val_left.value, val_right.value))

            raise SemanticError(f"Trying to use operator '{op}' on {val_left.type} and {val_right.type}")

        elif ctx.tableconstructor():
            return self.visit(ctx.tableconstructor())

        else:
            raise InternalError


    def visitParexp(self, ctx:TuaParser.ParexpContext):
        return self.visit(ctx.exp())


    def visitFunctionbody(self, ctx:TuaParser.FunctionbodyContext) -> tuple[list[Type], Type, TuaParser.BlockContext]:
        log.info("Functionbody")

        params = []
        if ctx.typednamelist():
            params = self.visit(ctx.typednamelist())

        type_ = self.visit(ctx.type_())
        return params, type_, ctx.block()


    def visitDostat(self, ctx:TuaParser.DostatContext):
        return self.visit(ctx.block())


    def visitWhilestat(self, ctx:TuaParser.WhilestatContext):
        condition = self.visit(ctx.exp())

        while condition.value:
            results = self.visit(ctx.block())
            if results is not None:
                return results
            condition = self.visit(ctx.exp())

        return None


    def visitIfstat(self, ctx:TuaParser.IfstatContext):
        n_exps = len(ctx.exp())
        n_blocks = len(ctx.block())

        # if and elseifs
        for i in range(n_exps):
            if self.visit(ctx.exp(i)).value:
                return self.visit(ctx.block(i))

        # else
        if n_blocks > n_exps:
            return self.visit(ctx.block(n_blocks - 1))


    def visitForintstat(self, ctx:TuaParser.ForintstatContext):
        # 'for' NAME '=' exp ',' exp (',' exp)? 'do' block 'end'
        iterator_name = ctx.getToken(TuaParser.NAME, 0).getText()
        iterator_value = self.visit(ctx.exp(0));

        if iterator_value.type.id != "int":
            raise SemanticError(f"Iterator '{iterator_name}' must be of type int")

        iterator_added_successfully = self.scope.new_identifier(iterator_name, iterator_value)

        if not iterator_added_successfully:
            raise SemanticError(f"Cannot use name '{iterator_name}' as iterator, because the identifier is already defined")

        change = 1
        if len(ctx.exp()) > 2:
            value = self.visit(ctx.exp(2))
            if value.type.id != "int":
                raise SemanticError(f"Cannot increment value of type int using value of type {value.type.id}")
            change = value.value

        while self.visit(ctx.exp(1)).value:
            results = self.visit(ctx.block())
            if results is not None:
                self.scope.del_identifier(iterator_name)
                return results

            iterator_value.value += change
            self.scope.change_value(iterator_name, iterator_value)


        self.scope.del_identifier(iterator_name)
        return None


    def visitForiteratorstat(self, ctx:TuaParser.ForiteratorstatContext):
        # 'for' NAME ',' NAME 'in' functioncall 'do' block 'end'
        generator = self.visit(ctx.functioncall())

        if not type(generator).__name__ == 'generator':
            raise SemanticError(f"In generic for loop functioncall must return generator")

        key_name = ctx.getToken(TuaParser.NAME, 0).getText()
        value_name = ctx.getToken(TuaParser.NAME, 1).getText()

        # check if the names can be used
        if self.scope.get(key_name) != None:
            raise SemanticError(f"Cannot use name '{key_name}' as iterator, because the identifier is already defined")

        if self.scope.get(value_name) != None:
            raise SemanticError(f"Cannot use name '{value_name}' as iterator, because the identifier is already defined")

        for elem in generator:
            # add new iterator variables every time, because values in table may be of different types
            # right now keys are always integers
            self.scope.new_identifier(key_name, Value(Type("int"), elem[0]))
            self.scope.new_identifier(value_name, elem[1])

            results = self.visit(ctx.block())

            # delete iterator variables
            self.scope.del_identifier(key_name)
            self.scope.del_identifier(value_name)

            if results is not None:
                return results

        return None


    def visitFunctiondef(self, ctx:TuaParser.FunctiondefContext):
        name = ctx.getToken(TuaParser.NAME, 0).getText()
        params, returns, block = self.visit(ctx.functionbody())
        # check if the returned value is of correct type !
        func = Function(name, returns, params, block)
        self.scope.new_identifier(name, Value(Type("function"), func))


    def visitLaststat(self, ctx:TuaParser.LaststatContext):
        log.info("Laststat")

        if ctx.return_():
            return self.visit(ctx.return_())
        else:
            raise NotImplementedError # break, continue

    def visitReturn(self, ctx:TuaParser.ReturnContext):
        if ctx.explist():
            result = self.visit(ctx.explist())
            # returns only the first element from explist
            return result[0]

        return Value(Type("nil"), None)


    def visitBreak(self, ctx:TuaParser.BreakContext):
        return self.visitChildren(ctx)


    def visitContinue(self, ctx:TuaParser.ContinueContext):
        return self.visitChildren(ctx)


    def visitTypednamelist(self, ctx:TuaParser.TypednamelistContext):
        log.info("Typednamelist")
        nametypes = []

        for c in ctx.nametype():
            name, type = self.visit(c)
            nametypes.append(Param(name, type))

        return nametypes

    def get_args(self, ctx:TuaParser.FunctioncallContext) -> list[Value]:
        if not ctx.explist():
            return []

        args: list[Value] = self.visit(ctx.explist())
        passed = list(map(lambda arg: arg.copy(), args))
        return passed

    def visitFunctioncall(self, ctx:TuaParser.FunctioncallContext):
        log.info(f"Functioncall")
        name = ctx.getToken(TuaParser.NAME, 0).getText()
        args = self.get_args(ctx)

        if name in self.builtins:
            return self.builtins[name](self, *args)
        else:
            func = self.scope.get(name)

            if func is None:
                raise SemanticError(f"Function '{name}' is not defined")

            if func.type.id != "function":
                raise SemanticError(f"Trying to call non-function '{name}'")

            funcval = func.value
            # check the number of arguments
            if len(args) != len(funcval.params):
                raise SemanticError(f"Wrong number of arguments when calling function '{name}'")

            function_scope = ScopeStack()
            # add all arguments to function scope
            for i in range(len(funcval.params)):
                # check type of the argument
                if args[i].type.id != funcval.params[i].type.id:
                    raise SemanticError(f"When calling function '{name}' parameter '{funcval.params[i].name}' should be of type {funcval.params[i].type}, got {args[i].type} instead")
                function_scope.new_identifier(funcval.params[i].name, args[i])

            # all functions are global - add them to scope
            for function in self.scope.get_functions():
                function_scope.new_identifier(function[0], function[1])

            # solution for scopestacks problem
            program_scope = self.scope
            self.scope = function_scope
            returns = self.visit(funcval.body)
            self.scope = program_scope

            if returns is None:
                returns = Value(Type("nil"), None)

            return returns


    def visitExplist(self, ctx:TuaParser.ExplistContext) -> list[Value]:
        log.info("Explist")
        vals = []
        for c in ctx.exp():
            vals.append(self.visit(c))
        return vals


    def visitTableconstructor(self, ctx:TuaParser.TableconstructorContext) -> Value:
        log.info("Tableconstructor")
        type = ""
        if ctx.fieldlist():
            fields, type = self.visit(ctx.fieldlist())
        else:
            fields = []
        tualist = TuaList(fields, type)

        return Value(Type(tualist.full_type_str()), tualist)


    def visitFieldlist(self, ctx:TuaParser.FieldlistContext):
        log.info("Fieldlist")
        children = []
        types = []
        for c in ctx.getChildren():
            if isinstance(c, TuaParser.FieldContext):
                child = self.visit(c)
                types.append(child.type.id)
                children.append(child)
        types = set(types)
        if len(types) > 1:
            raise SemanticError(f"Fieldlist contains multiple types: {sorted(types)}")
        return children, types.pop()


    def visitField(self, ctx:TuaParser.FieldContext):
        log.info("Field")
        return self.visitChildren(ctx)


    def visitBinopAddSub(self, ctx:TuaParser.BinopAddSubContext):
        log.info("BinopAddSub")
        return ctx.getText();


    def visitBinopMulDivMod(self, ctx:TuaParser.BinopMulDivModContext):
        log.info("BinopMulDivMod")
        return ctx.getText();


    def visitBinopComparison(self, ctx:TuaParser.BinopComparisonContext):
        log.info("BinopComparison")
        return ctx.getText();


    def visitBinopConcat(self, ctx:TuaParser.BinopConcatContext):
        log.info("BinopConcat")
        return ctx.getText();


    def visitBinopAnd(self, ctx:TuaParser.BinopAndContext):
        log.info("BinopAnd")
        return ctx.getText();


    def visitBinopOr(self, ctx:TuaParser.BinopOrContext):
        log.info("BinopOr")
        return ctx.getText();


    def visitBinopPower(self, ctx:TuaParser.BinopPowerContext):
        log.info("BinopPower")
        return ctx.getText();


    def visitUnop(self, ctx:TuaParser.UnopContext):
        log.info("Unop")
        return ctx.getText();


    def visitString(self, ctx:TuaParser.StringContext) -> Value:
        content =  ctx.getText()[1:-1] # skip quotes
        return Value(Type("string"), content)


    def visitNumber(self, ctx:TuaParser.NumberContext) -> Type:
        if ctx.INT():
            return int(ctx.getText()), Type("int")
        elif ctx.FLOAT():
            return float(ctx.getText()), Type("float")
        else:
            raise InternalError("Unknown number type")


    def visitBool(self, ctx:TuaParser.BoolContext):
        if ctx.TRUE():
            return True, Type("bool")
        if ctx.FALSE():
            return False, Type("bool")
