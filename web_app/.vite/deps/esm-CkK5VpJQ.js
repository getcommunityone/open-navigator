import { D as baggageEntryMetadataFromString, E as createContextKey, a as diag, n as trace, o as context, p as isSpanContextValid, r as propagation, y as TraceFlags } from "./esm-DubyGMwv.js";
import { Cn as ATTR_TELEMETRY_SDK_NAME, Fr as TELEMETRY_SDK_LANGUAGE_VALUE_WEBJS, Sn as ATTR_TELEMETRY_SDK_LANGUAGE, wn as ATTR_TELEMETRY_SDK_VERSION } from "./esm-Cg4aCtoK.js";
//#region node_modules/@opentelemetry/core/build/esm/trace/suppress-tracing.js
var SUPPRESS_TRACING_KEY = createContextKey("OpenTelemetry SDK Context Key SUPPRESS_TRACING");
function suppressTracing(context) {
	return context.setValue(SUPPRESS_TRACING_KEY, true);
}
function isTracingSuppressed(context) {
	return context.getValue(SUPPRESS_TRACING_KEY) === true;
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/baggage/constants.js
var BAGGAGE_HEADER = "baggage";
var BAGGAGE_MAX_PER_NAME_VALUE_PAIRS = 4096;
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/baggage/utils.js
function serializeKeyPairs(keyPairs) {
	return keyPairs.reduce((hValue, current) => {
		const value = `${hValue}${hValue !== "" ? "," : ""}${current}`;
		return value.length > 8192 ? hValue : value;
	}, "");
}
function getKeyPairs(baggage) {
	return baggage.getAllEntries().map(([key, value]) => {
		let entry = `${encodeURIComponent(key)}=${encodeURIComponent(value.value)}`;
		if (value.metadata !== void 0) entry += ";" + value.metadata.toString();
		return entry;
	});
}
function parsePairKeyValue(entry) {
	if (!entry) return;
	const metadataSeparatorIndex = entry.indexOf(";");
	const keyPairPart = metadataSeparatorIndex === -1 ? entry : entry.substring(0, metadataSeparatorIndex);
	const separatorIndex = keyPairPart.indexOf("=");
	if (separatorIndex <= 0) return;
	const rawKey = keyPairPart.substring(0, separatorIndex).trim();
	const rawValue = keyPairPart.substring(separatorIndex + 1).trim();
	if (!rawKey || !rawValue) return;
	let key;
	let value;
	try {
		key = decodeURIComponent(rawKey);
		value = decodeURIComponent(rawValue);
	} catch {
		return;
	}
	let metadata;
	if (metadataSeparatorIndex !== -1 && metadataSeparatorIndex < entry.length - 1) metadata = baggageEntryMetadataFromString(entry.substring(metadataSeparatorIndex + 1));
	return {
		key,
		value,
		metadata
	};
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/baggage/propagation/W3CBaggagePropagator.js
/**
* Propagates {@link Baggage} through Context format propagation.
*
* Based on the Baggage specification:
* https://w3c.github.io/baggage/
*/
var W3CBaggagePropagator = class {
	inject(context, carrier, setter) {
		const baggage = propagation.getBaggage(context);
		if (!baggage || isTracingSuppressed(context)) return;
		const headerValue = serializeKeyPairs(getKeyPairs(baggage).filter((pair) => {
			return pair.length <= BAGGAGE_MAX_PER_NAME_VALUE_PAIRS;
		}).slice(0, 180));
		if (headerValue.length > 0) setter.set(carrier, BAGGAGE_HEADER, headerValue);
	}
	extract(context, carrier, getter) {
		const headerValue = getter.get(carrier, BAGGAGE_HEADER);
		const baggageString = Array.isArray(headerValue) ? headerValue.join(",") : headerValue;
		if (!baggageString) return context;
		const baggage = {};
		if (baggageString.length === 0) return context;
		baggageString.split(",").forEach((entry) => {
			const keyPair = parsePairKeyValue(entry);
			if (keyPair) {
				const baggageEntry = { value: keyPair.value };
				if (keyPair.metadata) baggageEntry.metadata = keyPair.metadata;
				baggage[keyPair.key] = baggageEntry;
			}
		});
		if (Object.entries(baggage).length === 0) return context;
		return propagation.setBaggage(context, propagation.createBaggage(baggage));
	}
	fields() {
		return [BAGGAGE_HEADER];
	}
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/common/attributes.js
function sanitizeAttributes(attributes) {
	const out = {};
	if (typeof attributes !== "object" || attributes == null) return out;
	for (const key in attributes) {
		if (!Object.prototype.hasOwnProperty.call(attributes, key)) continue;
		if (!isAttributeKey(key)) {
			diag.warn(`Invalid attribute key: ${key}`);
			continue;
		}
		const val = attributes[key];
		if (!isAttributeValue(val)) {
			diag.warn(`Invalid attribute value set for key: ${key}`);
			continue;
		}
		if (Array.isArray(val)) out[key] = val.slice();
		else out[key] = val;
	}
	return out;
}
function isAttributeKey(key) {
	return typeof key === "string" && key !== "";
}
function isAttributeValue(val) {
	if (val == null) return true;
	if (Array.isArray(val)) return isHomogeneousAttributeValueArray(val);
	return isValidPrimitiveAttributeValueType(typeof val);
}
function isHomogeneousAttributeValueArray(arr) {
	let type;
	for (const element of arr) {
		if (element == null) continue;
		const elementType = typeof element;
		if (elementType === type) continue;
		if (!type) {
			if (isValidPrimitiveAttributeValueType(elementType)) {
				type = elementType;
				continue;
			}
			return false;
		}
		return false;
	}
	return true;
}
function isValidPrimitiveAttributeValueType(valType) {
	switch (valType) {
		case "number":
		case "boolean":
		case "string": return true;
	}
	return false;
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/common/logging-error-handler.js
/**
* Returns a function that logs an error using the provided logger, or a
* console logger if one was not provided.
*/
function loggingErrorHandler() {
	return (ex) => {
		diag.error(stringifyException(ex));
	};
}
/**
* Converts an exception into a string representation
* @param {Exception} ex
*/
function stringifyException(ex) {
	if (typeof ex === "string") return ex;
	else return JSON.stringify(flattenException(ex));
}
/**
* Flattens an exception into key-value pairs by traversing the prototype chain
* and coercing values to strings. Duplicate properties will not be overwritten;
* the first insert wins.
*/
function flattenException(ex) {
	const result = {};
	let current = ex;
	while (current !== null) {
		Object.getOwnPropertyNames(current).forEach((propertyName) => {
			if (result[propertyName]) return;
			const value = current[propertyName];
			if (value) result[propertyName] = String(value);
		});
		current = Object.getPrototypeOf(current);
	}
	return result;
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/common/global-error-handler.js
/** The global error handler delegate */
var delegateHandler = loggingErrorHandler();
/**
* Return the global error handler
* @param {Exception} ex
*/
function globalErrorHandler(ex) {
	try {
		delegateHandler(ex);
	} catch {}
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/platform/browser/environment.js
function getStringFromEnv(_) {}
function getNumberFromEnv(_) {}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/version.js
var VERSION$1 = "2.7.1";
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/semconv.js
/**
* The name of the runtime of this process.
*
* @example OpenJDK Runtime Environment
*
* @experimental This attribute is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*/
var ATTR_PROCESS_RUNTIME_NAME = "process.runtime.name";
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/platform/browser/sdk-info.js
/** Constants describing the SDK in use */
var SDK_INFO = {
	[ATTR_TELEMETRY_SDK_NAME]: "opentelemetry",
	[ATTR_PROCESS_RUNTIME_NAME]: "browser",
	[ATTR_TELEMETRY_SDK_LANGUAGE]: TELEMETRY_SDK_LANGUAGE_VALUE_WEBJS,
	[ATTR_TELEMETRY_SDK_VERSION]: VERSION$1
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/platform/browser/index.js
/**
* @deprecated Use performance directly.
*/
var otperformance = performance;
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/common/time.js
var NANOSECOND_DIGITS = 9;
var MILLISECONDS_TO_NANOSECONDS = Math.pow(10, 6);
var SECOND_TO_NANOSECONDS = Math.pow(10, NANOSECOND_DIGITS);
/**
* Converts a number of milliseconds from epoch to HrTime([seconds, remainder in nanoseconds]).
* @param epochMillis
*/
function millisToHrTime(epochMillis) {
	const epochSeconds = epochMillis / 1e3;
	return [Math.trunc(epochSeconds), Math.round(epochMillis % 1e3 * MILLISECONDS_TO_NANOSECONDS)];
}
/**
* Returns an hrtime calculated via performance component.
* @param performanceNow
*/
function hrTime(performanceNow) {
	return addHrTimes(millisToHrTime(otperformance.timeOrigin), millisToHrTime(typeof performanceNow === "number" ? performanceNow : otperformance.now()));
}
/**
*
* Converts a TimeInput to an HrTime, defaults to _hrtime().
* @param time
*/
function timeInputToHrTime(time) {
	if (isTimeInputHrTime(time)) return time;
	else if (typeof time === "number") if (time < otperformance.timeOrigin) return hrTime(time);
	else return millisToHrTime(time);
	else if (time instanceof Date) return millisToHrTime(time.getTime());
	else throw TypeError("Invalid input type");
}
/**
* Returns a duration of two hrTime.
* @param startTime
* @param endTime
*/
function hrTimeDuration(startTime, endTime) {
	let seconds = endTime[0] - startTime[0];
	let nanos = endTime[1] - startTime[1];
	if (nanos < 0) {
		seconds -= 1;
		nanos += SECOND_TO_NANOSECONDS;
	}
	return [seconds, nanos];
}
/**
* Convert hrTime to nanoseconds.
* @param time
*/
function hrTimeToNanoseconds(time) {
	return time[0] * SECOND_TO_NANOSECONDS + time[1];
}
/**
* Convert hrTime to microseconds.
* @param time
*/
function hrTimeToMicroseconds(time) {
	return time[0] * 1e6 + time[1] / 1e3;
}
/**
* check if time is HrTime
* @param value
*/
function isTimeInputHrTime(value) {
	return Array.isArray(value) && value.length === 2 && typeof value[0] === "number" && typeof value[1] === "number";
}
/**
* check if input value is a correct types.TimeInput
* @param value
*/
function isTimeInput(value) {
	return isTimeInputHrTime(value) || typeof value === "number" || value instanceof Date;
}
/**
* Given 2 HrTime formatted times, return their sum as an HrTime.
*/
function addHrTimes(time1, time2) {
	const out = [time1[0] + time2[0], time1[1] + time2[1]];
	if (out[1] >= SECOND_TO_NANOSECONDS) {
		out[1] -= SECOND_TO_NANOSECONDS;
		out[0] += 1;
	}
	return out;
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/ExportResult.js
var ExportResultCode;
(function(ExportResultCode) {
	ExportResultCode[ExportResultCode["SUCCESS"] = 0] = "SUCCESS";
	ExportResultCode[ExportResultCode["FAILED"] = 1] = "FAILED";
})(ExportResultCode || (ExportResultCode = {}));
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/propagation/composite.js
/** Combines multiple propagators into a single propagator. */
var CompositePropagator = class {
	_propagators;
	_fields;
	/**
	* Construct a composite propagator from a list of propagators.
	*
	* @param [config] Configuration object for composite propagator
	*/
	constructor(config = {}) {
		this._propagators = config.propagators ?? [];
		const fields = /* @__PURE__ */ new Set();
		for (const propagator of this._propagators) {
			const propagatorFields = typeof propagator.fields === "function" ? propagator.fields() : [];
			for (const field of propagatorFields) fields.add(field);
		}
		this._fields = Array.from(fields);
	}
	/**
	* Run each of the configured propagators with the given context and carrier.
	* Propagators are run in the order they are configured, so if multiple
	* propagators write the same carrier key, the propagator later in the list
	* will "win".
	*
	* @param context Context to inject
	* @param carrier Carrier into which context will be injected
	*/
	inject(context, carrier, setter) {
		for (const propagator of this._propagators) try {
			propagator.inject(context, carrier, setter);
		} catch (err) {
			diag.warn(`Failed to inject with ${propagator.constructor.name}. Err: ${err.message}`);
		}
	}
	/**
	* Run each of the configured propagators with the given context and carrier.
	* Propagators are run in the order they are configured, so if multiple
	* propagators write the same context key, the propagator later in the list
	* will "win".
	*
	* @param context Context to add values to
	* @param carrier Carrier from which to extract context
	*/
	extract(context, carrier, getter) {
		return this._propagators.reduce((ctx, propagator) => {
			try {
				return propagator.extract(ctx, carrier, getter);
			} catch (err) {
				diag.warn(`Failed to extract with ${propagator.constructor.name}. Err: ${err.message}`);
			}
			return ctx;
		}, context);
	}
	fields() {
		return this._fields.slice();
	}
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/internal/validators.js
var VALID_KEY_CHAR_RANGE = "[_0-9a-z-*/]";
var VALID_KEY_REGEX = new RegExp(`^(?:${`[a-z]${VALID_KEY_CHAR_RANGE}{0,255}`}|${`[a-z0-9]${VALID_KEY_CHAR_RANGE}{0,240}@[a-z]${VALID_KEY_CHAR_RANGE}{0,13}`})$`);
var VALID_VALUE_BASE_REGEX = /^[ -~]{0,255}[!-~]$/;
var INVALID_VALUE_COMMA_EQUAL_REGEX = /,|=/;
/**
* Key is opaque string up to 256 characters printable. It MUST begin with a
* lowercase letter, and can only contain lowercase letters a-z, digits 0-9,
* underscores _, dashes -, asterisks *, and forward slashes /.
* For multi-tenant vendor scenarios, an at sign (@) can be used to prefix the
* vendor name. Vendors SHOULD set the tenant ID at the beginning of the key.
* see https://www.w3.org/TR/trace-context/#key
*/
function validateKey(key) {
	return VALID_KEY_REGEX.test(key);
}
/**
* Value is opaque string up to 256 characters printable ASCII RFC0020
* characters (i.e., the range 0x20 to 0x7E) except comma , and =.
*/
function validateValue(value) {
	return VALID_VALUE_BASE_REGEX.test(value) && !INVALID_VALUE_COMMA_EQUAL_REGEX.test(value);
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/trace/TraceState.js
var MAX_TRACE_STATE_ITEMS = 32;
var MAX_TRACE_STATE_LEN = 512;
var LIST_MEMBERS_SEPARATOR = ",";
var LIST_MEMBER_KEY_VALUE_SPLITTER = "=";
/**
* TraceState must be a class and not a simple object type because of the spec
* requirement (https://www.w3.org/TR/trace-context/#tracestate-field).
*
* Here is the list of allowed mutations:
* - New key-value pair should be added into the beginning of the list
* - The value of any key can be updated. Modified keys MUST be moved to the
* beginning of the list.
*/
var TraceState = class TraceState {
	_length;
	_rawTraceState;
	_internalState;
	constructor(rawTraceState) {
		this._rawTraceState = typeof rawTraceState === "string" ? rawTraceState : "";
		this._length = this._rawTraceState.length;
	}
	set(key, value) {
		if (!validateKey(key) || !validateValue(value)) return this;
		const currState = this._getState();
		const currValue = currState.get(key);
		let newLength = this._length;
		if (typeof currValue === "string") newLength += value.length - currValue.length;
		else newLength += key.length + value.length + (currState.size > 0 ? 2 : 1);
		if (newLength > MAX_TRACE_STATE_LEN) return this;
		const newState = new Map(currState);
		newState.delete(key);
		newState.set(key, value);
		return this._fromState(newState, newLength);
	}
	unset(key) {
		const currState = this._getState();
		const currValue = currState.get(key);
		if (typeof currValue !== "string") return this;
		let newLength = this._length - (key.length + currValue.length + 1);
		if (currState.size > 1) newLength = newLength - 1;
		const newState = new Map(currState);
		newState.delete(key);
		return this._fromState(newState, newLength);
	}
	get(key) {
		return this._getState().get(key);
	}
	serialize() {
		let serialized = "";
		let index = 0;
		for (const entry of this._getState()) {
			if (index > 0) serialized = LIST_MEMBERS_SEPARATOR + serialized;
			serialized = `${entry[0]}${LIST_MEMBER_KEY_VALUE_SPLITTER}${entry[1]}` + serialized;
			index++;
		}
		return serialized;
	}
	_getState() {
		if (this._internalState) return this._internalState;
		const vendorMembers = this._rawTraceState.split(LIST_MEMBERS_SEPARATOR);
		const vendorEntries = /* @__PURE__ */ new Map();
		let currentLength = 0;
		for (const member of vendorMembers) {
			const m = member.trim();
			const idx = m.indexOf(LIST_MEMBER_KEY_VALUE_SPLITTER);
			if (idx === -1) continue;
			const key = m.slice(0, idx);
			const value = m.slice(idx + 1);
			if (!validateKey(key) || !validateValue(value)) continue;
			const futureLength = currentLength + m.length + (vendorEntries.size > 0 ? 1 : 0);
			if (futureLength > MAX_TRACE_STATE_LEN) continue;
			vendorEntries.set(key, value);
			currentLength = futureLength;
			if (vendorEntries.size >= MAX_TRACE_STATE_ITEMS) break;
		}
		this._length = currentLength;
		this._internalState = new Map(Array.from(vendorEntries.entries()).reverse());
		return this._internalState;
	}
	_fromState(state, length) {
		const traceState = Object.create(TraceState.prototype);
		traceState._internalState = state;
		traceState._length = length;
		return traceState;
	}
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/trace/W3CTraceContextPropagator.js
var TRACE_PARENT_HEADER = "traceparent";
var TRACE_STATE_HEADER = "tracestate";
var VERSION = "00";
var TRACE_PARENT_REGEX = new RegExp(`^\\s?((?!ff)[\\da-f]{2})-((?![0]{32})[\\da-f]{32})-((?![0]{16})[\\da-f]{16})-([\\da-f]{2})(-.*)?\\s?$`);
/**
* Parses information from the [traceparent] span tag and converts it into {@link SpanContext}
* @param traceParent - A meta property that comes from server.
*     It should be dynamically generated server side to have the server's request trace Id,
*     a parent span Id that was set on the server's request span,
*     and the trace flags to indicate the server's sampling decision
*     (01 = sampled, 00 = not sampled).
*     for example: '{version}-{traceId}-{spanId}-{sampleDecision}'
*     For more information see {@link https://www.w3.org/TR/trace-context/}
*/
function parseTraceParent(traceParent) {
	const match = TRACE_PARENT_REGEX.exec(traceParent);
	if (!match) return null;
	if (match[1] === "00" && match[5]) return null;
	return {
		traceId: match[2],
		spanId: match[3],
		traceFlags: parseInt(match[4], 16)
	};
}
/**
* Propagates {@link SpanContext} through Trace Context format propagation.
*
* Based on the Trace Context specification:
* https://www.w3.org/TR/trace-context/
*/
var W3CTraceContextPropagator = class {
	inject(context, carrier, setter) {
		const spanContext = trace.getSpanContext(context);
		if (!spanContext || isTracingSuppressed(context) || !isSpanContextValid(spanContext)) return;
		const traceParent = `${VERSION}-${spanContext.traceId}-${spanContext.spanId}-0${Number(spanContext.traceFlags || TraceFlags.NONE).toString(16)}`;
		setter.set(carrier, TRACE_PARENT_HEADER, traceParent);
		if (spanContext.traceState) setter.set(carrier, TRACE_STATE_HEADER, spanContext.traceState.serialize());
	}
	extract(context, carrier, getter) {
		const traceParentHeader = getter.get(carrier, TRACE_PARENT_HEADER);
		if (!traceParentHeader) return context;
		const traceParent = Array.isArray(traceParentHeader) ? traceParentHeader[0] : traceParentHeader;
		if (typeof traceParent !== "string") return context;
		const spanContext = parseTraceParent(traceParent);
		if (!spanContext) return context;
		spanContext.isRemote = true;
		const traceStateHeader = getter.get(carrier, TRACE_STATE_HEADER);
		if (traceStateHeader) {
			const state = Array.isArray(traceStateHeader) ? traceStateHeader.join(",") : traceStateHeader;
			spanContext.traceState = new TraceState(typeof state === "string" ? state : void 0);
		}
		return trace.setSpanContext(context, spanContext);
	}
	fields() {
		return [TRACE_PARENT_HEADER, TRACE_STATE_HEADER];
	}
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/utils/lodash.merge.js
/**
* based on lodash in order to support esm builds without esModuleInterop.
* lodash is using MIT License.
**/
var objectTag = "[object Object]";
var nullTag = "[object Null]";
var undefinedTag = "[object Undefined]";
var funcToString = Function.prototype.toString;
var objectCtorString = funcToString.call(Object);
var getPrototypeOf = Object.getPrototypeOf;
var objectProto = Object.prototype;
var hasOwnProperty = objectProto.hasOwnProperty;
var symToStringTag = Symbol ? Symbol.toStringTag : void 0;
var nativeObjectToString = objectProto.toString;
/**
* Checks if `value` is a plain object, that is, an object created by the
* `Object` constructor or one with a `[[Prototype]]` of `null`.
*
* @static
* @memberOf _
* @since 0.8.0
* @category Lang
* @param {*} value The value to check.
* @returns {boolean} Returns `true` if `value` is a plain object, else `false`.
* @example
*
* function Foo() {
*   this.a = 1;
* }
*
* _.isPlainObject(new Foo);
* // => false
*
* _.isPlainObject([1, 2, 3]);
* // => false
*
* _.isPlainObject({ 'x': 0, 'y': 0 });
* // => true
*
* _.isPlainObject(Object.create(null));
* // => true
*/
function isPlainObject(value) {
	if (!isObjectLike(value) || baseGetTag(value) !== objectTag) return false;
	const proto = getPrototypeOf(value);
	if (proto === null) return true;
	const Ctor = hasOwnProperty.call(proto, "constructor") && proto.constructor;
	return typeof Ctor == "function" && Ctor instanceof Ctor && funcToString.call(Ctor) === objectCtorString;
}
/**
* Checks if `value` is object-like. A value is object-like if it's not `null`
* and has a `typeof` result of "object".
*
* @static
* @memberOf _
* @since 4.0.0
* @category Lang
* @param {*} value The value to check.
* @returns {boolean} Returns `true` if `value` is object-like, else `false`.
* @example
*
* _.isObjectLike({});
* // => true
*
* _.isObjectLike([1, 2, 3]);
* // => true
*
* _.isObjectLike(_.noop);
* // => false
*
* _.isObjectLike(null);
* // => false
*/
function isObjectLike(value) {
	return value != null && typeof value == "object";
}
/**
* The base implementation of `getTag` without fallbacks for buggy environments.
*
* @private
* @param {*} value The value to query.
* @returns {string} Returns the `toStringTag`.
*/
function baseGetTag(value) {
	if (value == null) return value === void 0 ? undefinedTag : nullTag;
	return symToStringTag && symToStringTag in Object(value) ? getRawTag(value) : objectToString(value);
}
/**
* A specialized version of `baseGetTag` which ignores `Symbol.toStringTag` values.
*
* @private
* @param {*} value The value to query.
* @returns {string} Returns the raw `toStringTag`.
*/
function getRawTag(value) {
	const isOwn = hasOwnProperty.call(value, symToStringTag), tag = value[symToStringTag];
	let unmasked = false;
	try {
		value[symToStringTag] = void 0;
		unmasked = true;
	} catch {}
	const result = nativeObjectToString.call(value);
	if (unmasked) if (isOwn) value[symToStringTag] = tag;
	else delete value[symToStringTag];
	return result;
}
/**
* Converts `value` to a string using `Object.prototype.toString`.
*
* @private
* @param {*} value The value to convert.
* @returns {string} Returns the converted string.
*/
function objectToString(value) {
	return nativeObjectToString.call(value);
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/utils/merge.js
var MAX_LEVEL = 20;
/**
* Merges objects together
* @param args - objects / values to be merged
*/
function merge(...args) {
	let result = args.shift();
	const objects = /* @__PURE__ */ new WeakMap();
	while (args.length > 0) result = mergeTwoObjects(result, args.shift(), 0, objects);
	return result;
}
function takeValue(value) {
	if (isArray(value)) return value.slice();
	return value;
}
/**
* Merges two objects
* @param one - first object
* @param two - second object
* @param level - current deep level
* @param objects - objects holder that has been already referenced - to prevent
* cyclic dependency
*/
function mergeTwoObjects(one, two, level = 0, objects) {
	let result;
	if (level > MAX_LEVEL) return;
	level++;
	if (isPrimitive(one) || isPrimitive(two) || isFunction(two)) result = takeValue(two);
	else if (isArray(one)) {
		result = one.slice();
		if (isArray(two)) for (let i = 0, j = two.length; i < j; i++) result.push(takeValue(two[i]));
		else if (isObject(two)) {
			const keys = Object.keys(two);
			for (let i = 0, j = keys.length; i < j; i++) {
				const key = keys[i];
				if (key === "__proto__" || key === "constructor" || key === "prototype") continue;
				result[key] = takeValue(two[key]);
			}
		}
	} else if (isObject(one)) if (isObject(two)) {
		if (!shouldMerge(one, two)) return two;
		result = Object.assign({}, one);
		const keys = Object.keys(two);
		for (let i = 0, j = keys.length; i < j; i++) {
			const key = keys[i];
			if (key === "__proto__" || key === "constructor" || key === "prototype") continue;
			const twoValue = two[key];
			if (isPrimitive(twoValue)) if (typeof twoValue === "undefined") delete result[key];
			else result[key] = twoValue;
			else {
				const obj1 = result[key];
				const obj2 = twoValue;
				if (wasObjectReferenced(one, key, objects) || wasObjectReferenced(two, key, objects)) delete result[key];
				else {
					if (isObject(obj1) && isObject(obj2)) {
						const arr1 = objects.get(obj1) || [];
						const arr2 = objects.get(obj2) || [];
						arr1.push({
							obj: one,
							key
						});
						arr2.push({
							obj: two,
							key
						});
						objects.set(obj1, arr1);
						objects.set(obj2, arr2);
					}
					result[key] = mergeTwoObjects(result[key], twoValue, level, objects);
				}
			}
		}
	} else result = two;
	return result;
}
/**
* Function to check if object has been already reference
* @param obj
* @param key
* @param objects
*/
function wasObjectReferenced(obj, key, objects) {
	const arr = objects.get(obj[key]) || [];
	for (let i = 0, j = arr.length; i < j; i++) {
		const info = arr[i];
		if (info.key === key && info.obj === obj) return true;
	}
	return false;
}
function isArray(value) {
	return Array.isArray(value);
}
function isFunction(value) {
	return typeof value === "function";
}
function isObject(value) {
	return !isPrimitive(value) && !isArray(value) && !isFunction(value) && typeof value === "object";
}
function isPrimitive(value) {
	return typeof value === "string" || typeof value === "number" || typeof value === "boolean" || typeof value === "undefined" || value instanceof Date || value instanceof RegExp || value === null;
}
function shouldMerge(one, two) {
	if (!isPlainObject(one) || !isPlainObject(two)) return false;
	return true;
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/utils/url.js
function urlMatches(url, urlToMatch) {
	if (typeof urlToMatch === "string") return url === urlToMatch;
	else return !!url.match(urlToMatch);
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/utils/promise.js
var Deferred = class {
	_promise;
	_resolve;
	_reject;
	constructor() {
		this._promise = new Promise((resolve, reject) => {
			this._resolve = resolve;
			this._reject = reject;
		});
	}
	get promise() {
		return this._promise;
	}
	resolve(val) {
		this._resolve(val);
	}
	reject(err) {
		this._reject(err);
	}
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/utils/callback.js
/**
* Bind the callback and only invoke the callback once regardless how many times `BindOnceFuture.call` is invoked.
*/
var BindOnceFuture = class {
	_isCalled = false;
	_deferred = new Deferred();
	_callback;
	_that;
	constructor(callback, that) {
		this._callback = callback;
		this._that = that;
	}
	get isCalled() {
		return this._isCalled;
	}
	get promise() {
		return this._deferred.promise;
	}
	call(...args) {
		if (!this._isCalled) {
			this._isCalled = true;
			try {
				Promise.resolve(this._callback.call(this._that, ...args)).then((val) => this._deferred.resolve(val), (err) => this._deferred.reject(err));
			} catch (err) {
				this._deferred.reject(err);
			}
		}
		return this._deferred.promise;
	}
};
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/internal/exporter.js
/**
* @internal
* Shared functionality used by Exporters while exporting data, including suppression of Traces.
*/
function _export(exporter, arg) {
	return new Promise((resolve) => {
		context.with(suppressTracing(context.active()), () => {
			exporter.export(arg, resolve);
		});
	});
}
//#endregion
//#region node_modules/@opentelemetry/core/build/esm/index.js
var internal = { _export };
//#endregion
export { sanitizeAttributes as C, suppressTracing as E, isAttributeValue as S, isTracingSuppressed as T, otperformance as _, W3CTraceContextPropagator as a, getStringFromEnv as b, addHrTimes as c, hrTimeToMicroseconds as d, hrTimeToNanoseconds as f, timeInputToHrTime as g, millisToHrTime as h, merge as i, hrTime as l, isTimeInputHrTime as m, BindOnceFuture as n, CompositePropagator as o, isTimeInput as p, urlMatches as r, ExportResultCode as s, internal as t, hrTimeDuration as u, SDK_INFO as v, W3CBaggagePropagator as w, globalErrorHandler as x, getNumberFromEnv as y };

//# sourceMappingURL=esm-CkK5VpJQ.js.map