import { a as diag } from "./esm-DubyGMwv.js";
import { f as hrTimeToNanoseconds, s as ExportResultCode } from "./esm-CkK5VpJQ.js";
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/OTLPExporterBase.js
var OTLPExporterBase = class {
	_delegate;
	constructor(delegate) {
		this._delegate = delegate;
	}
	/**
	* Export items.
	* @param items
	* @param resultCallback
	*/
	export(items, resultCallback) {
		this._delegate.export(items, resultCallback);
	}
	forceFlush() {
		return this._delegate.forceFlush();
	}
	shutdown() {
		return this._delegate.shutdown();
	}
};
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/types.js
/**
* Interface for handling error
*/
var OTLPExporterError = class extends Error {
	code;
	name = "OTLPExporterError";
	data;
	constructor(message, code, data) {
		super(message);
		this.data = data;
		this.code = code;
	}
};
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/configuration/shared-configuration.js
function validateTimeoutMillis(timeoutMillis) {
	if (Number.isFinite(timeoutMillis) && timeoutMillis > 0) return timeoutMillis;
	throw new Error(`Configuration: timeoutMillis is invalid, expected number greater than 0 (actual: '${timeoutMillis}')`);
}
function wrapStaticHeadersInFunction(headers) {
	if (headers == null) return;
	return async () => headers;
}
/**
* @param userProvidedConfiguration  Configuration options provided by the user in code.
* @param fallbackConfiguration Fallback to use when the {@link userProvidedConfiguration} does not specify an option.
* @param defaultConfiguration The defaults as defined by the exporter specification
*/
function mergeOtlpSharedConfigurationWithDefaults(userProvidedConfiguration, fallbackConfiguration, defaultConfiguration) {
	return {
		timeoutMillis: validateTimeoutMillis(userProvidedConfiguration.timeoutMillis ?? fallbackConfiguration.timeoutMillis ?? defaultConfiguration.timeoutMillis),
		concurrencyLimit: userProvidedConfiguration.concurrencyLimit ?? fallbackConfiguration.concurrencyLimit ?? defaultConfiguration.concurrencyLimit,
		compression: userProvidedConfiguration.compression ?? fallbackConfiguration.compression ?? defaultConfiguration.compression
	};
}
function getSharedConfigurationDefaults() {
	return {
		timeoutMillis: 1e4,
		concurrencyLimit: 30,
		compression: "none"
	};
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/bounded-queue-export-promise-handler.js
var BoundedQueueExportPromiseHandler = class {
	_concurrencyLimit;
	_sendingPromises = [];
	/**
	* @param concurrencyLimit maximum promises allowed in a queue at the same time.
	*/
	constructor(concurrencyLimit) {
		this._concurrencyLimit = concurrencyLimit;
	}
	pushPromise(promise) {
		if (this.hasReachedLimit()) throw new Error("Concurrency Limit reached");
		this._sendingPromises.push(promise);
		const popPromise = () => {
			const index = this._sendingPromises.indexOf(promise);
			this._sendingPromises.splice(index, 1);
		};
		promise.then(popPromise, popPromise);
	}
	hasReachedLimit() {
		return this._sendingPromises.length >= this._concurrencyLimit;
	}
	async awaitAll() {
		await Promise.all(this._sendingPromises);
	}
};
/**
* Promise queue for keeping track of export promises. Finished promises will be auto-dequeued.
* Allows for awaiting all promises in the queue.
*/
function createBoundedQueueExportPromiseHandler(options) {
	return new BoundedQueueExportPromiseHandler(options.concurrencyLimit);
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/logging-response-handler.js
function isPartialSuccessResponse(response) {
	return Object.prototype.hasOwnProperty.call(response, "partialSuccess");
}
/**
* Default response handler that logs a partial success to the console.
*/
function createLoggingPartialSuccessResponseHandler() {
	return { handleResponse(response) {
		if (response == null || !isPartialSuccessResponse(response) || response.partialSuccess == null || Object.keys(response.partialSuccess).length === 0) return;
		diag.warn("Received Partial Success response:", JSON.stringify(response.partialSuccess));
	} };
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/otlp-export-delegate.js
var OTLPExportDelegate = class {
	_diagLogger;
	_transport;
	_serializer;
	_responseHandler;
	_promiseQueue;
	_timeout;
	constructor(transport, serializer, responseHandler, promiseQueue, timeout) {
		this._transport = transport;
		this._serializer = serializer;
		this._responseHandler = responseHandler;
		this._promiseQueue = promiseQueue;
		this._timeout = timeout;
		this._diagLogger = diag.createComponentLogger({ namespace: "OTLPExportDelegate" });
	}
	export(internalRepresentation, resultCallback) {
		this._diagLogger.debug("items to be sent", internalRepresentation);
		if (this._promiseQueue.hasReachedLimit()) {
			resultCallback({
				code: ExportResultCode.FAILED,
				error: /* @__PURE__ */ new Error("Concurrent export limit reached")
			});
			return;
		}
		const serializedRequest = this._serializer.serializeRequest(internalRepresentation);
		if (serializedRequest == null) {
			resultCallback({
				code: ExportResultCode.FAILED,
				error: /* @__PURE__ */ new Error("Nothing to send")
			});
			return;
		}
		this._promiseQueue.pushPromise(this._transport.send(serializedRequest, this._timeout).then((response) => {
			if (response.status === "success") {
				if (response.data != null) try {
					this._responseHandler.handleResponse(this._serializer.deserializeResponse(response.data));
				} catch (e) {
					this._diagLogger.warn("Export succeeded but could not deserialize response - is the response specification compliant?", e, response.data);
				}
				resultCallback({ code: ExportResultCode.SUCCESS });
				return;
			} else if (response.status === "failure" && response.error) {
				resultCallback({
					code: ExportResultCode.FAILED,
					error: response.error
				});
				return;
			} else if (response.status === "retryable") resultCallback({
				code: ExportResultCode.FAILED,
				error: response.error ?? new OTLPExporterError("Export failed with retryable status")
			});
			else resultCallback({
				code: ExportResultCode.FAILED,
				error: new OTLPExporterError("Export failed with unknown error")
			});
		}, (reason) => resultCallback({
			code: ExportResultCode.FAILED,
			error: reason
		})));
	}
	forceFlush() {
		return this._promiseQueue.awaitAll();
	}
	async shutdown() {
		this._diagLogger.debug("shutdown started");
		await this.forceFlush();
		this._transport.shutdown();
	}
};
/**
* Creates a generic delegate for OTLP exports which only contains parts of the OTLP export that are shared across all
* signals.
*/
function createOtlpExportDelegate(components, settings) {
	return new OTLPExportDelegate(components.transport, components.serializer, createLoggingPartialSuccessResponseHandler(), components.promiseHandler, settings.timeout);
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/otlp-network-export-delegate.js
function createOtlpNetworkExportDelegate(options, serializer, transport) {
	return createOtlpExportDelegate({
		transport,
		serializer,
		promiseHandler: createBoundedQueueExportPromiseHandler(options)
	}, { timeout: options.timeoutMillis });
}
//#endregion
//#region node_modules/@opentelemetry/otlp-transformer/build/esm/common/internal.js
function createResource(resource, encoder) {
	const result = {
		attributes: toAttributes(resource.attributes, encoder),
		droppedAttributesCount: 0
	};
	const schemaUrl = resource.schemaUrl;
	if (schemaUrl && schemaUrl !== "") result.schemaUrl = schemaUrl;
	return result;
}
function createInstrumentationScope(scope) {
	return {
		name: scope.name,
		version: scope.version
	};
}
function toAttributes(attributes, encoder) {
	return Object.keys(attributes).map((key) => toKeyValue(key, attributes[key], encoder));
}
function toKeyValue(key, value, encoder) {
	return {
		key,
		value: toAnyValue(value, encoder)
	};
}
function toAnyValue(value, encoder) {
	const t = typeof value;
	if (t === "string") return { stringValue: value };
	if (t === "number") {
		if (!Number.isInteger(value)) return { doubleValue: value };
		return { intValue: value };
	}
	if (t === "boolean") return { boolValue: value };
	if (value instanceof Uint8Array) return { bytesValue: encoder.encodeUint8Array(value) };
	if (Array.isArray(value)) {
		const values = new Array(value.length);
		for (let i = 0; i < value.length; i++) values[i] = toAnyValue(value[i], encoder);
		return { arrayValue: { values } };
	}
	if (t === "object" && value != null) {
		const keys = Object.keys(value);
		const values = new Array(keys.length);
		for (let i = 0; i < keys.length; i++) values[i] = {
			key: keys[i],
			value: toAnyValue(value[keys[i]], encoder)
		};
		return { kvlistValue: { values } };
	}
	return {};
}
//#endregion
//#region node_modules/@opentelemetry/otlp-transformer/build/esm/common/utils.js
function hrTimeToNanos(hrTime) {
	const NANOSECONDS = BigInt(1e9);
	return BigInt(Math.trunc(hrTime[0])) * NANOSECONDS + BigInt(Math.trunc(hrTime[1]));
}
function encodeAsString(hrTime) {
	return hrTimeToNanos(hrTime).toString();
}
var encodeTimestamp = typeof BigInt !== "undefined" ? encodeAsString : hrTimeToNanoseconds;
function identity(value) {
	return value;
}
/**
* Encoder for JSON format.
* Uses string timestamps, hex for span/trace IDs, and base64 for Uint8Array.
*/
var JSON_ENCODER = {
	encodeHrTime: encodeTimestamp,
	encodeSpanContext: identity,
	encodeOptionalSpanContext: identity,
	encodeUint8Array: (bytes) => {
		if (typeof Buffer !== "undefined") return Buffer.from(bytes).toString("base64");
		const chars = new Array(bytes.length);
		for (let i = 0; i < bytes.length; i++) chars[i] = String.fromCharCode(bytes[i]);
		return btoa(chars.join(""));
	}
};
//#endregion
//#region node_modules/@opentelemetry/otlp-transformer/build/esm/trace/internal.js
var SPAN_FLAGS_CONTEXT_HAS_IS_REMOTE_MASK = 256;
var SPAN_FLAGS_CONTEXT_IS_REMOTE_MASK = 512;
/**
* Builds the 32-bit span flags value combining the low 8-bit W3C TraceFlags
* with the HAS_IS_REMOTE and IS_REMOTE bits according to the OTLP spec.
*/
function buildSpanFlagsFrom(traceFlags, isRemote) {
	let flags = traceFlags & 255 | SPAN_FLAGS_CONTEXT_HAS_IS_REMOTE_MASK;
	if (isRemote) flags |= SPAN_FLAGS_CONTEXT_IS_REMOTE_MASK;
	return flags;
}
function sdkSpanToOtlpSpan(span, encoder) {
	const ctx = span.spanContext();
	const status = span.status;
	const parentSpanId = span.parentSpanContext?.spanId ? encoder.encodeSpanContext(span.parentSpanContext?.spanId) : void 0;
	return {
		traceId: encoder.encodeSpanContext(ctx.traceId),
		spanId: encoder.encodeSpanContext(ctx.spanId),
		parentSpanId,
		traceState: ctx.traceState?.serialize(),
		name: span.name,
		kind: span.kind == null ? 0 : span.kind + 1,
		startTimeUnixNano: encoder.encodeHrTime(span.startTime),
		endTimeUnixNano: encoder.encodeHrTime(span.endTime),
		attributes: toAttributes(span.attributes, encoder),
		droppedAttributesCount: span.droppedAttributesCount,
		events: span.events.map((event) => toOtlpSpanEvent(event, encoder)),
		droppedEventsCount: span.droppedEventsCount,
		status: {
			code: status.code,
			message: status.message
		},
		links: span.links.map((link) => toOtlpLink(link, encoder)),
		droppedLinksCount: span.droppedLinksCount,
		flags: buildSpanFlagsFrom(ctx.traceFlags, span.parentSpanContext?.isRemote)
	};
}
function toOtlpLink(link, encoder) {
	return {
		attributes: link.attributes ? toAttributes(link.attributes, encoder) : [],
		spanId: encoder.encodeSpanContext(link.context.spanId),
		traceId: encoder.encodeSpanContext(link.context.traceId),
		traceState: link.context.traceState?.serialize(),
		droppedAttributesCount: link.droppedAttributesCount || 0,
		flags: buildSpanFlagsFrom(link.context.traceFlags, link.context.isRemote)
	};
}
function toOtlpSpanEvent(timedEvent, encoder) {
	return {
		attributes: timedEvent.attributes ? toAttributes(timedEvent.attributes, encoder) : [],
		name: timedEvent.name,
		timeUnixNano: encoder.encodeHrTime(timedEvent.time),
		droppedAttributesCount: timedEvent.droppedAttributesCount || 0
	};
}
function createExportTraceServiceRequest(spans, encoder) {
	return { resourceSpans: spanRecordsToResourceSpans(spans, encoder) };
}
function createResourceMap(readableSpans) {
	const resourceMap = /* @__PURE__ */ new Map();
	for (const record of readableSpans) {
		let ilsMap = resourceMap.get(record.resource);
		if (!ilsMap) {
			ilsMap = /* @__PURE__ */ new Map();
			resourceMap.set(record.resource, ilsMap);
		}
		const instrumentationScopeKey = `${record.instrumentationScope.name}@${record.instrumentationScope.version || ""}:${record.instrumentationScope.schemaUrl || ""}`;
		let records = ilsMap.get(instrumentationScopeKey);
		if (!records) {
			records = [];
			ilsMap.set(instrumentationScopeKey, records);
		}
		records.push(record);
	}
	return resourceMap;
}
function spanRecordsToResourceSpans(readableSpans, encoder) {
	const resourceMap = createResourceMap(readableSpans);
	const out = [];
	const entryIterator = resourceMap.entries();
	let entry = entryIterator.next();
	while (!entry.done) {
		const [resource, ilmMap] = entry.value;
		const scopeResourceSpans = [];
		const ilmIterator = ilmMap.values();
		let ilmEntry = ilmIterator.next();
		while (!ilmEntry.done) {
			const scopeSpans = ilmEntry.value;
			if (scopeSpans.length > 0) {
				const spans = scopeSpans.map((readableSpan) => sdkSpanToOtlpSpan(readableSpan, encoder));
				scopeResourceSpans.push({
					scope: createInstrumentationScope(scopeSpans[0].instrumentationScope),
					spans,
					schemaUrl: scopeSpans[0].instrumentationScope.schemaUrl
				});
			}
			ilmEntry = ilmIterator.next();
		}
		const processedResource = createResource(resource, encoder);
		const transformedSpans = {
			resource: processedResource,
			scopeSpans: scopeResourceSpans,
			schemaUrl: processedResource.schemaUrl
		};
		out.push(transformedSpans);
		entry = entryIterator.next();
	}
	return out;
}
//#endregion
//#region node_modules/@opentelemetry/otlp-transformer/build/esm/trace/json/trace.js
var JsonTraceSerializer = {
	serializeRequest: (arg) => {
		const request = createExportTraceServiceRequest(arg, JSON_ENCODER);
		return new TextEncoder().encode(JSON.stringify(request));
	},
	deserializeResponse: (arg) => {
		if (arg.length === 0) return {};
		const decoder = new TextDecoder();
		try {
			return JSON.parse(decoder.decode(arg));
		} catch (err) {
			diag.warn(`Failed to parse trace export response: ${err.message}. Returning empty response`);
			return {};
		}
	}
};
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/retrying-transport.js
var MAX_ATTEMPTS = 5;
var INITIAL_BACKOFF = 1e3;
var MAX_BACKOFF = 5e3;
var BACKOFF_MULTIPLIER = 1.5;
var JITTER = .2;
/**
* Get a pseudo-random jitter that falls in the range of [-JITTER, +JITTER]
*/
function getJitter() {
	return Math.random() * (2 * JITTER) - JITTER;
}
var RetryingTransport = class {
	_transport;
	constructor(transport) {
		this._transport = transport;
	}
	retry(data, timeoutMillis, inMillis) {
		return new Promise((resolve, reject) => {
			setTimeout(() => {
				this._transport.send(data, timeoutMillis).then(resolve, reject);
			}, inMillis);
		});
	}
	async send(data, timeoutMillis) {
		let attempts = MAX_ATTEMPTS;
		let nextBackoff = INITIAL_BACKOFF;
		const deadline = Date.now() + timeoutMillis;
		let result = await this._transport.send(data, timeoutMillis);
		while (result.status === "retryable" && attempts > 0) {
			attempts--;
			const backoff = Math.max(Math.min(nextBackoff * (1 + getJitter()), MAX_BACKOFF), 0);
			nextBackoff = nextBackoff * BACKOFF_MULTIPLIER;
			const retryInMillis = result.retryInMillis ?? backoff;
			const remainingTimeoutMillis = deadline - Date.now();
			if (retryInMillis > remainingTimeoutMillis) {
				diag.info(`Export retry time ${Math.round(retryInMillis)}ms exceeds remaining timeout ${Math.round(remainingTimeoutMillis)}ms, not retrying further.`);
				return result;
			}
			diag.verbose(`Scheduling export retry in ${Math.round(retryInMillis)}ms`);
			result = await this.retry(data, remainingTimeoutMillis, retryInMillis);
		}
		if (result.status === "success") diag.verbose(`Export succeeded after ${MAX_ATTEMPTS - attempts} retry attempts.`);
		else if (result.status === "retryable") diag.info(`Export failed after maximum retry attempts (${MAX_ATTEMPTS}).`);
		else diag.info(`Export failed with non-retryable error: ${result.error}`);
		return result;
	}
	shutdown() {
		return this._transport.shutdown();
	}
};
/**
* Creates an Exporter Transport that retries on 'retryable' response.
*/
function createRetryingTransport(options) {
	return new RetryingTransport(options.transport);
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/is-export-retryable.js
function isExportHTTPErrorRetryable(statusCode) {
	return statusCode === 429 || statusCode === 502 || statusCode === 503 || statusCode === 504;
}
function parseRetryAfterToMills(retryAfter) {
	if (retryAfter == null) return;
	const seconds = Number.parseInt(retryAfter, 10);
	if (Number.isInteger(seconds)) return seconds > 0 ? seconds * 1e3 : -1;
	const delay = new Date(retryAfter).getTime() - Date.now();
	if (delay >= 0) return delay;
	return 0;
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/transport/fetch-transport.js
/**
* Maximum total body size for concurrent keepalive requests.
* Browsers enforce a 64KiB cumulative limit across all pending keepalive requests.
* We use 60KB to leave headroom for headers.
* @see https://github.com/whatwg/fetch/issues/679
* @see https://blog.huli.tw/2025/01/06/en/navigator-sendbeacon-64kib-and-source-code/
*/
var MAX_KEEPALIVE_BODY_SIZE = 60 * 1024;
/**
* Maximum concurrent keepalive requests.
* Chrome enforces 9 concurrent keepalive fetch requests per renderer process.
* @see https://github.com/whatwg/fetch/issues/679
* Quote: "If the renderer process is processing more than 9 requests with keepalive set, we reject a new request"
*/
var MAX_KEEPALIVE_REQUESTS = 9;
/**
* Track cumulative pending body size across all in-flight keepalive requests.
* This is necessary because the 64KiB limit is cumulative, not per-request.
*/
var pendingBodySize = 0;
/**
* Track number of pending keepalive requests.
*/
var pendingKeepaliveCount = 0;
var FetchTransport = class {
	_parameters;
	constructor(parameters) {
		this._parameters = parameters;
	}
	async send(data, timeoutMillis) {
		const abortController = new AbortController();
		const timeout = setTimeout(() => abortController.abort(), timeoutMillis);
		let fetchApi = globalThis.fetch;
		if (typeof fetchApi.__original === "function") fetchApi = fetchApi.__original;
		const requestSize = data.byteLength;
		const wouldExceedSize = pendingBodySize + requestSize > MAX_KEEPALIVE_BODY_SIZE;
		const useKeepalive = !wouldExceedSize && !(pendingKeepaliveCount >= MAX_KEEPALIVE_REQUESTS);
		if (useKeepalive) {
			pendingBodySize += requestSize;
			pendingKeepaliveCount++;
		} else {
			const reason = wouldExceedSize ? "size limit" : "count limit";
			diag.debug(`keepalive disabled: ${(requestSize / 1024).toFixed(1)}KB payload, ${pendingKeepaliveCount} pending (${reason})`);
		}
		try {
			const url = new URL(this._parameters.url);
			const response = await fetchApi(url.href, {
				method: "POST",
				headers: await this._parameters.headers(),
				body: data,
				signal: abortController.signal,
				keepalive: useKeepalive,
				mode: globalThis.location ? globalThis.location.origin === url.origin ? "same-origin" : "cors" : "no-cors"
			});
			if (response.status >= 200 && response.status <= 299) {
				diag.debug(`export response success (status: ${response.status})`);
				return { status: "success" };
			} else if (isExportHTTPErrorRetryable(response.status)) {
				diag.warn(`export response retryable (status: ${response.status})`);
				return {
					status: "retryable",
					retryInMillis: parseRetryAfterToMills(response.headers.get("Retry-After"))
				};
			}
			diag.error(`export response failure (status: ${response.status})`);
			return {
				status: "failure",
				error: /* @__PURE__ */ new Error(`Fetch request failed with non-retryable status ${response.status}`)
			};
		} catch (error) {
			if (isFetchNetworkErrorRetryable(error)) {
				diag.warn(`export request retryable (network error: ${error})`);
				return {
					status: "retryable",
					error: new Error("Fetch request encountered a network error", { cause: error })
				};
			}
			diag.error(`export request failure (error: ${error})`);
			return {
				status: "failure",
				error: new Error("Fetch request errored", { cause: error })
			};
		} finally {
			clearTimeout(timeout);
			if (useKeepalive) {
				pendingBodySize -= requestSize;
				pendingKeepaliveCount--;
			}
		}
	}
	shutdown() {}
};
/**
* Creates an exporter transport that uses `fetch` to send the data
* @param parameters applied to each request made by transport
*/
function createFetchTransport(parameters) {
	return new FetchTransport(parameters);
}
function isFetchNetworkErrorRetryable(error) {
	return error instanceof TypeError && !error.cause;
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/otlp-browser-http-export-delegate.js
function createOtlpFetchExportDelegate(options, serializer) {
	return createOtlpNetworkExportDelegate(options, serializer, createRetryingTransport({ transport: createFetchTransport(options) }));
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/util.js
/**
* Parses headers from config leaving only those that have defined values
* @param partialHeaders
*/
function validateAndNormalizeHeaders(partialHeaders) {
	const headers = {};
	Object.entries(partialHeaders ?? {}).forEach(([key, value]) => {
		if (typeof value !== "undefined") headers[key] = String(value);
		else diag.warn(`Header "${key}" has invalid value (${value}) and will be ignored`);
	});
	return headers;
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/configuration/otlp-http-configuration.js
function mergeHeaders(userProvidedHeaders, fallbackHeaders, defaultHeaders) {
	return async () => {
		const requiredHeaders = { ...await defaultHeaders() };
		const headers = {};
		if (fallbackHeaders != null) Object.assign(headers, await fallbackHeaders());
		if (userProvidedHeaders != null) Object.assign(headers, validateAndNormalizeHeaders(await userProvidedHeaders()));
		return Object.assign(headers, requiredHeaders);
	};
}
function validateUserProvidedUrl(url) {
	if (url == null) return;
	try {
		const base = globalThis.location?.href;
		return new URL(url, base).href;
	} catch {
		throw new Error(`Configuration: Could not parse user-provided export URL: '${url}'`);
	}
}
/**
* @param userProvidedConfiguration  Configuration options provided by the user in code.
* @param fallbackConfiguration Fallback to use when the {@link userProvidedConfiguration} does not specify an option.
* @param defaultConfiguration The defaults as defined by the exporter specification
*/
function mergeOtlpHttpConfigurationWithDefaults(userProvidedConfiguration, fallbackConfiguration, defaultConfiguration) {
	return {
		...mergeOtlpSharedConfigurationWithDefaults(userProvidedConfiguration, fallbackConfiguration, defaultConfiguration),
		headers: mergeHeaders(userProvidedConfiguration.headers, fallbackConfiguration.headers, defaultConfiguration.headers),
		url: validateUserProvidedUrl(userProvidedConfiguration.url) ?? fallbackConfiguration.url ?? defaultConfiguration.url
	};
}
function getHttpConfigurationDefaults(requiredHeaders, signalResourcePath) {
	return {
		...getSharedConfigurationDefaults(),
		headers: async () => requiredHeaders,
		url: "http://localhost:4318/" + signalResourcePath
	};
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/configuration/convert-legacy-http-options.js
function convertLegacyHeaders(config) {
	if (typeof config.headers === "function") return config.headers;
	return wrapStaticHeadersInFunction(config.headers);
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/configuration/convert-legacy-browser-http-options.js
/**
* @deprecated this will be removed in 2.0
*
* @param config
* @param signalResourcePath
* @param requiredHeaders
*/
function convertLegacyBrowserHttpOptions(config, signalResourcePath, requiredHeaders) {
	return mergeOtlpHttpConfigurationWithDefaults({
		url: config.url,
		timeoutMillis: config.timeoutMillis,
		headers: convertLegacyHeaders(config),
		concurrencyLimit: config.concurrencyLimit
	}, {}, getHttpConfigurationDefaults(requiredHeaders, signalResourcePath));
}
//#endregion
//#region node_modules/@opentelemetry/otlp-exporter-base/build/esm/configuration/create-legacy-browser-delegate.js
/**
* @deprecated
* @param config
* @param serializer
* @param signalResourcePath
* @param requiredHeaders
*/
function createLegacyOtlpBrowserExportDelegate(config, serializer, signalResourcePath, requiredHeaders) {
	return createOtlpFetchExportDelegate(convertLegacyBrowserHttpOptions(config, signalResourcePath, requiredHeaders), serializer);
}
//#endregion
//#region node_modules/@opentelemetry/exporter-trace-otlp-http/build/esm/platform/browser/OTLPTraceExporter.js
/**
* Collector Trace Exporter for Web
*/
var OTLPTraceExporter = class extends OTLPExporterBase {
	constructor(config = {}) {
		super(createLegacyOtlpBrowserExportDelegate(config, JsonTraceSerializer, "v1/traces", { "Content-Type": "application/json" }));
	}
};
//#endregion
export { OTLPTraceExporter };

//# sourceMappingURL=@opentelemetry_exporter-trace-otlp-http.js.map