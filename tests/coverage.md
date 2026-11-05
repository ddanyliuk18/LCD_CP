# Rule coverage

Fixtures without a directory prefix are in `e2e` (positive) or
`semantic_invalid` (negative). The original Stage 1 fixtures stay unchanged.

| Rule | Follows the rule | Breaks the rule |
|---|---|---|
| Declaration before use, no global capture | lookup | undeclared, global_capture |
| One variable per scope; nested shadowing | branches | duplicate |
| Mutable bindings/immutable parameters | integers, recursion | immutable_parameter |
| Signed integer widths and widening | integers, forward | narrowing, literal_overflow |
| Compile-time overflow and runtime overflow checks | integers; runtime_overflow expects termination | constant_overflow |
| Integer-only arithmetic | integers | string_add |
| Integer/flag comparison, flag-only negation/condition | flags, branches | string_equal, not_string, condition |
| Typed calls, exact arity, nested/forward calls | forward | too_many, too_few, argument_type |
| Recursion and final typed retrocede | recursion | return_type; missing_return |
| Ordered typed complete card initializers | card, nested | initializer_count, initializer_type |
| Field existence and mutable chain at every link | nested | unknown_field, constant_base, constant_field, constant_middle |
| Member calls, implicit fields and member-before-global lookup | members, lookup | global_capture, member_argument |
| Mutation propagation and constant receivers | members | mutating_const, transitive_mutation, nested_mutation |
| Recursive card value layout forbidden | nested | recursive_card |
| Immutable objects allow read-only calls | lookup | mutating_const |
| draw consumes stdin; Engrave prints values with one newline | read, integers, flags, strings, card | draw_argument, engrave_value |
| String bindings/assignment/fields/parameters/results/member results | strings, string_serves | string_assign, argument_type, return_type, initializer_type |
| Exactly four string escapes; valid UTF-8 | strings | bad_escape, unclosed_string |
| No string comparison/arithmetic/coercions | strings, string_serves | string_equal, string_add, string_assign |
| Required syntax/positions and Stage 1 compatibility | all 16 original valid AST fixtures | all 18 original invalid fixtures |
| Function passed as an argument and called inside | higher_order_argument | higher_order_argument_type, higher_order_serve_type |
| Returned lambda keeps its captured values; computed calls | higher_order_returned, higher_order_recursion | higher_order_not_function |
| Capture by value, read-only copies | higher_order_copy, higher_order_fields | higher_order_assign_captured, higher_order_assign_captured_field, higher_order_mutating_capture |
| Function types in fields, widening at value calls | higher_order_fields, higher_order_types | higher_order_arity, higher_order_call_argument, higher_order_declared_type, higher_order_unknown_type |
| Lambda bodies: result type, parameters, names | higher_order_types, higher_order_shadow | higher_order_lambda_return, higher_order_duplicate_parameter, higher_order_self_reference, higher_order_member_in_lambda, higher_order_compare |
| Lambda and function type syntax | all higher_order programs | higher_order_missing_arrow, higher_order_missing_return, higher_order_type_without_result |
| Unused variables: cascade, scopes, kept effects | optimizer/unused_variables_*, optimizer_keeps_overflow | |
| Unused functions: chains, cycles, members, values | optimizer/unused_functions_* | |
| Inlining: names, order, sites, closures, shapes left alone | optimizer/inline_* | |

Printing's exact bytes (including raw string fields, `%` in strings, Unicode,
all escapes and recursive card formatting) are asserted by `.expected` files.
These are output contracts: deviations are caught by golden comparisons rather
than rejected source programs. Likewise forward-call visibility is a positive
resolution rule; its negative counterpart is an unknown serve.
