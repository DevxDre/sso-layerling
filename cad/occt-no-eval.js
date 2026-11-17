/* Inserted inside the pinned Emscripten module in place of its code generators. */
function craftInvokerFunction(humanName, argTypes, classType, cppInvoker, cppTarget) {
  if (argTypes.length < 2) {
    throwBindingError("An Embind signature must declare its return and receiver types");
  }
  const [returnType, receiverType, ...parameterTypes] = argTypes;
  const hasReceiver = receiverType !== null && classType !== null;
  const needsStack = usesDestructorStack(argTypes);
  const wireTypes = hasReceiver ? [receiverType, ...parameterTypes] : parameterTypes;

  return createNamedFunction(humanName, function (...parameters) {
    const destructors = needsStack ? [] : null;
    const wireValues = wireTypes.map((type, index) => {
      const value = hasReceiver && index === 0 ? this : parameters[index - Number(hasReceiver)];
      return type.toWireType(destructors, value);
    });
    const result = cppInvoker(cppTarget, ...wireValues);
    if (destructors) {
      runDestructors(destructors);
    } else {
      wireTypes.forEach((type, index) => {
        const destroy = type.destructorFunction;
        if (destroy !== null) destroy(wireValues[index]);
      });
    }
    return returnType.isVoid ? undefined : returnType.fromWireType(result);
  });
}

function createEmvalInvoker(argCount, argTypesPtr, kind) {
  const [returnType, ...parameterTypes] = emval_lookupTypes(argCount, argTypesPtr >>> 0);
  const toReturnWire = returnType.toWireType.bind(returnType);
  const wireSize = 8;
  const invoke = (handle, methodName, destructorsRef, args) => {
    const values = parameterTypes.map((type, index) => type.readValueFromPointer(args + index * wireSize));
    let result;
    switch (kind) {
      case 0: result = Emval.toValue(handle)(...values); break;
      case 1: result = Emval.toValue(handle)[getStringOrSymbol(methodName)](...values); break;
      case 2: result = Reflect.construct(Emval.toValue(handle), values); break;
      case 3: result = values.at(-1); break;
      default: throwBindingError("Unsupported Emval invoker kind");
    }
    return returnType.isVoid ? undefined : emval_returnValue(toReturnWire, destructorsRef, result);
  };
  const name = `methodCaller<(${parameterTypes.map(type => type.name)}) => ${returnType.name}>`;
  return emval_addMethodCaller(createNamedFunction(name, invoke));
}
