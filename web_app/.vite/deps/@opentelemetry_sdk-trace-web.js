import { C as createNoopMeter, T as ROOT_CONTEXT, _ as INVALID_SPAN_CONTEXT, a as diag, c as SpanStatusCode, h as isValidTraceId, l as SpanKind, n as trace, o as context, p as isSpanContextValid, r as propagation, u as SamplingDecision$1, y as TraceFlags } from "./esm-DubyGMwv.js";
import { C as sanitizeAttributes, E as suppressTracing, S as isAttributeValue, T as isTracingSuppressed, _ as otperformance, a as W3CTraceContextPropagator, b as getStringFromEnv, c as addHrTimes, d as hrTimeToMicroseconds, f as hrTimeToNanoseconds, g as timeInputToHrTime, h as millisToHrTime, i as merge, l as hrTime, m as isTimeInputHrTime, n as BindOnceFuture, o as CompositePropagator, p as isTimeInput, r as urlMatches, s as ExportResultCode, t as internal, u as hrTimeDuration, w as W3CBaggagePropagator, x as globalErrorHandler, y as getNumberFromEnv } from "./esm-CkK5VpJQ.js";
import { Lt as ATTR_EXCEPTION_MESSAGE, Rt as ATTR_EXCEPTION_STACKTRACE, zt as ATTR_EXCEPTION_TYPE } from "./esm-Cg4aCtoK.js";
import { s as defaultResource } from "./esm-BqDCjizk.js";
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/enums.js
var ExceptionEventName = "exception";
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/Span.js
/**
* This class represents a span.
*/
var SpanImpl = class {
	_spanContext;
	kind;
	parentSpanContext;
	attributes = {};
	links = [];
	events = [];
	startTime;
	resource;
	instrumentationScope;
	_droppedAttributesCount = 0;
	_droppedEventsCount = 0;
	_droppedLinksCount = 0;
	_attributesCount = 0;
	name;
	status = { code: SpanStatusCode.UNSET };
	endTime = [0, 0];
	_ended = false;
	_duration = [-1, -1];
	_spanProcessor;
	_spanLimits;
	_attributeValueLengthLimit;
	_recordEndMetrics;
	_performanceStartTime;
	_performanceOffset;
	_startTimeProvided;
	/**
	* Constructs a new SpanImpl instance.
	*/
	constructor(opts) {
		const now = Date.now();
		this._spanContext = opts.spanContext;
		this._performanceStartTime = otperformance.now();
		this._performanceOffset = now - (this._performanceStartTime + otperformance.timeOrigin);
		this._startTimeProvided = opts.startTime != null;
		this._spanLimits = opts.spanLimits;
		this._attributeValueLengthLimit = this._spanLimits.attributeValueLengthLimit ?? 0;
		this._spanProcessor = opts.spanProcessor;
		this.name = opts.name;
		this.parentSpanContext = opts.parentSpanContext;
		this.kind = opts.kind;
		if (opts.links) for (const link of opts.links) this.addLink(link);
		this.startTime = this._getTime(opts.startTime ?? now);
		this.resource = opts.resource;
		this.instrumentationScope = opts.scope;
		this._recordEndMetrics = opts.recordEndMetrics;
		if (opts.attributes != null) this.setAttributes(opts.attributes);
		this._spanProcessor.onStart(this, opts.context);
	}
	spanContext() {
		return this._spanContext;
	}
	setAttribute(key, value) {
		if (value == null || this._isSpanEnded()) return this;
		if (key.length === 0) {
			diag.warn(`Invalid attribute key: ${key}`);
			return this;
		}
		if (!isAttributeValue(value)) {
			diag.warn(`Invalid attribute value set for key: ${key}`);
			return this;
		}
		const { attributeCountLimit } = this._spanLimits;
		const isNewKey = !Object.prototype.hasOwnProperty.call(this.attributes, key);
		if (attributeCountLimit !== void 0 && this._attributesCount >= attributeCountLimit && isNewKey) {
			this._droppedAttributesCount++;
			return this;
		}
		this.attributes[key] = this._truncateToSize(value);
		if (isNewKey) this._attributesCount++;
		return this;
	}
	setAttributes(attributes) {
		for (const key in attributes) if (Object.prototype.hasOwnProperty.call(attributes, key)) this.setAttribute(key, attributes[key]);
		return this;
	}
	/**
	*
	* @param name Span Name
	* @param [attributesOrStartTime] Span attributes or start time
	*     if type is {@type TimeInput} and 3rd param is undefined
	* @param [timeStamp] Specified time stamp for the event
	*/
	addEvent(name, attributesOrStartTime, timeStamp) {
		if (this._isSpanEnded()) return this;
		const { eventCountLimit } = this._spanLimits;
		if (eventCountLimit === 0) {
			diag.warn("No events allowed.");
			this._droppedEventsCount++;
			return this;
		}
		if (eventCountLimit !== void 0 && this.events.length >= eventCountLimit) {
			if (this._droppedEventsCount === 0) diag.debug("Dropping extra events.");
			this.events.shift();
			this._droppedEventsCount++;
		}
		if (isTimeInput(attributesOrStartTime)) {
			if (!isTimeInput(timeStamp)) timeStamp = attributesOrStartTime;
			attributesOrStartTime = void 0;
		}
		const sanitized = sanitizeAttributes(attributesOrStartTime);
		const { attributePerEventCountLimit } = this._spanLimits;
		const attributes = {};
		let droppedAttributesCount = 0;
		let eventAttributesCount = 0;
		for (const attr in sanitized) {
			if (!Object.prototype.hasOwnProperty.call(sanitized, attr)) continue;
			const attrVal = sanitized[attr];
			if (attributePerEventCountLimit !== void 0 && eventAttributesCount >= attributePerEventCountLimit) {
				droppedAttributesCount++;
				continue;
			}
			attributes[attr] = this._truncateToSize(attrVal);
			eventAttributesCount++;
		}
		this.events.push({
			name,
			attributes,
			time: this._getTime(timeStamp),
			droppedAttributesCount
		});
		return this;
	}
	addLink(link) {
		if (this._isSpanEnded()) return this;
		const { linkCountLimit } = this._spanLimits;
		if (linkCountLimit === 0) {
			this._droppedLinksCount++;
			return this;
		}
		if (linkCountLimit !== void 0 && this.links.length >= linkCountLimit) {
			if (this._droppedLinksCount === 0) diag.debug("Dropping extra links.");
			this.links.shift();
			this._droppedLinksCount++;
		}
		const { attributePerLinkCountLimit } = this._spanLimits;
		const sanitized = sanitizeAttributes(link.attributes);
		const attributes = {};
		let droppedAttributesCount = 0;
		let linkAttributesCount = 0;
		for (const attr in sanitized) {
			if (!Object.prototype.hasOwnProperty.call(sanitized, attr)) continue;
			const attrVal = sanitized[attr];
			if (attributePerLinkCountLimit !== void 0 && linkAttributesCount >= attributePerLinkCountLimit) {
				droppedAttributesCount++;
				continue;
			}
			attributes[attr] = this._truncateToSize(attrVal);
			linkAttributesCount++;
		}
		const processedLink = { context: link.context };
		if (linkAttributesCount > 0) processedLink.attributes = attributes;
		if (droppedAttributesCount > 0) processedLink.droppedAttributesCount = droppedAttributesCount;
		this.links.push(processedLink);
		return this;
	}
	addLinks(links) {
		for (const link of links) this.addLink(link);
		return this;
	}
	setStatus(status) {
		if (this._isSpanEnded()) return this;
		if (status.code === SpanStatusCode.UNSET) return this;
		if (this.status.code === SpanStatusCode.OK) return this;
		const newStatus = { code: status.code };
		if (status.code === SpanStatusCode.ERROR) {
			if (typeof status.message === "string") newStatus.message = status.message;
			else if (status.message != null) diag.warn(`Dropping invalid status.message of type '${typeof status.message}', expected 'string'`);
		}
		this.status = newStatus;
		return this;
	}
	updateName(name) {
		if (this._isSpanEnded()) return this;
		this.name = name;
		return this;
	}
	end(endTime) {
		if (this._isSpanEnded()) {
			diag.error(`${this.name} ${this._spanContext.traceId}-${this._spanContext.spanId} - You can only call end() on a span once.`);
			return;
		}
		this.endTime = this._getTime(endTime);
		this._duration = hrTimeDuration(this.startTime, this.endTime);
		if (this._duration[0] < 0) {
			diag.warn("Inconsistent start and end time, startTime > endTime. Setting span duration to 0ms.", this.startTime, this.endTime);
			this.endTime = this.startTime.slice();
			this._duration = [0, 0];
		}
		if (this._droppedEventsCount > 0) diag.warn(`Dropped ${this._droppedEventsCount} events because eventCountLimit reached`);
		if (this._droppedLinksCount > 0) diag.warn(`Dropped ${this._droppedLinksCount} links because linkCountLimit reached`);
		if (this._spanProcessor.onEnding) this._spanProcessor.onEnding(this);
		this._recordEndMetrics?.();
		this._ended = true;
		this._spanProcessor.onEnd(this);
	}
	_getTime(inp) {
		if (typeof inp === "number" && inp <= otperformance.now()) return hrTime(inp + this._performanceOffset);
		if (typeof inp === "number") return millisToHrTime(inp);
		if (inp instanceof Date) return millisToHrTime(inp.getTime());
		if (isTimeInputHrTime(inp)) return inp;
		if (this._startTimeProvided) return millisToHrTime(Date.now());
		const msDuration = otperformance.now() - this._performanceStartTime;
		return addHrTimes(this.startTime, millisToHrTime(msDuration));
	}
	isRecording() {
		return this._ended === false;
	}
	recordException(exception, time) {
		const attributes = {};
		if (typeof exception === "string") attributes[ATTR_EXCEPTION_MESSAGE] = exception;
		else if (exception) {
			if (exception.code) attributes[ATTR_EXCEPTION_TYPE] = exception.code.toString();
			else if (exception.name) attributes[ATTR_EXCEPTION_TYPE] = exception.name;
			if (exception.message) attributes[ATTR_EXCEPTION_MESSAGE] = exception.message;
			if (exception.stack) attributes[ATTR_EXCEPTION_STACKTRACE] = exception.stack;
		}
		if (attributes["exception.type"] || attributes["exception.message"]) this.addEvent(ExceptionEventName, attributes, time);
		else diag.warn(`Failed to record an exception ${exception}`);
	}
	get duration() {
		return this._duration;
	}
	get ended() {
		return this._ended;
	}
	get droppedAttributesCount() {
		return this._droppedAttributesCount;
	}
	get droppedEventsCount() {
		return this._droppedEventsCount;
	}
	get droppedLinksCount() {
		return this._droppedLinksCount;
	}
	_isSpanEnded() {
		if (this._ended) {
			const error = /* @__PURE__ */ new Error(`Operation attempted on ended Span {traceId: ${this._spanContext.traceId}, spanId: ${this._spanContext.spanId}}`);
			diag.warn(`Cannot execute the operation on ended Span {traceId: ${this._spanContext.traceId}, spanId: ${this._spanContext.spanId}}`, error);
		}
		return this._ended;
	}
	_truncateToLimitUtil(value, limit) {
		if (value.length <= limit) return value;
		return value.substring(0, limit);
	}
	/**
	* If the given attribute value is of type string and has more characters than given {@code attributeValueLengthLimit} then
	* return string with truncated to {@code attributeValueLengthLimit} characters
	*
	* If the given attribute value is array of strings then
	* return new array of strings with each element truncated to {@code attributeValueLengthLimit} characters
	*
	* Otherwise return same Attribute {@code value}
	*
	* @param value Attribute value
	* @returns truncated attribute value if required, otherwise same value
	*/
	_truncateToSize(value) {
		const limit = this._attributeValueLengthLimit;
		if (limit <= 0) {
			diag.warn(`Attribute value limit must be positive, got ${limit}`);
			return value;
		}
		if (typeof value === "string") return this._truncateToLimitUtil(value, limit);
		if (Array.isArray(value)) return value.map((val) => typeof val === "string" ? this._truncateToLimitUtil(val, limit) : val);
		return value;
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/Sampler.js
/**
* A sampling decision that determines how a {@link Span} will be recorded
* and collected.
*/
var SamplingDecision;
(function(SamplingDecision) {
	/**
	* `Span.isRecording() === false`, span will not be recorded and all events
	* and attributes will be dropped.
	*/
	SamplingDecision[SamplingDecision["NOT_RECORD"] = 0] = "NOT_RECORD";
	/**
	* `Span.isRecording() === true`, but `Sampled` flag in {@link TraceFlags}
	* MUST NOT be set.
	*/
	SamplingDecision[SamplingDecision["RECORD"] = 1] = "RECORD";
	/**
	* `Span.isRecording() === true` AND `Sampled` flag in {@link TraceFlags}
	* MUST be set.
	*/
	SamplingDecision[SamplingDecision["RECORD_AND_SAMPLED"] = 2] = "RECORD_AND_SAMPLED";
})(SamplingDecision || (SamplingDecision = {}));
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/sampler/AlwaysOffSampler.js
/** Sampler that samples no traces. */
var AlwaysOffSampler = class {
	shouldSample() {
		return { decision: SamplingDecision.NOT_RECORD };
	}
	toString() {
		return "AlwaysOffSampler";
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/sampler/AlwaysOnSampler.js
/** Sampler that samples all traces. */
var AlwaysOnSampler = class {
	shouldSample() {
		return { decision: SamplingDecision.RECORD_AND_SAMPLED };
	}
	toString() {
		return "AlwaysOnSampler";
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/sampler/ParentBasedSampler.js
/**
* A composite sampler that either respects the parent span's sampling decision
* or delegates to `delegateSampler` for root spans.
*/
var ParentBasedSampler = class {
	_root;
	_remoteParentSampled;
	_remoteParentNotSampled;
	_localParentSampled;
	_localParentNotSampled;
	constructor(config) {
		this._root = config.root;
		if (!this._root) {
			globalErrorHandler(/* @__PURE__ */ new Error("ParentBasedSampler must have a root sampler configured"));
			this._root = new AlwaysOnSampler();
		}
		this._remoteParentSampled = config.remoteParentSampled ?? new AlwaysOnSampler();
		this._remoteParentNotSampled = config.remoteParentNotSampled ?? new AlwaysOffSampler();
		this._localParentSampled = config.localParentSampled ?? new AlwaysOnSampler();
		this._localParentNotSampled = config.localParentNotSampled ?? new AlwaysOffSampler();
	}
	shouldSample(context, traceId, spanName, spanKind, attributes, links) {
		const parentContext = trace.getSpanContext(context);
		if (!parentContext || !isSpanContextValid(parentContext)) return this._root.shouldSample(context, traceId, spanName, spanKind, attributes, links);
		if (parentContext.isRemote) {
			if (parentContext.traceFlags & TraceFlags.SAMPLED) return this._remoteParentSampled.shouldSample(context, traceId, spanName, spanKind, attributes, links);
			return this._remoteParentNotSampled.shouldSample(context, traceId, spanName, spanKind, attributes, links);
		}
		if (parentContext.traceFlags & TraceFlags.SAMPLED) return this._localParentSampled.shouldSample(context, traceId, spanName, spanKind, attributes, links);
		return this._localParentNotSampled.shouldSample(context, traceId, spanName, spanKind, attributes, links);
	}
	toString() {
		return `ParentBased{root=${this._root.toString()}, remoteParentSampled=${this._remoteParentSampled.toString()}, remoteParentNotSampled=${this._remoteParentNotSampled.toString()}, localParentSampled=${this._localParentSampled.toString()}, localParentNotSampled=${this._localParentNotSampled.toString()}}`;
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/sampler/TraceIdRatioBasedSampler.js
/** Sampler that samples a given fraction of traces based of trace id deterministically. */
var TraceIdRatioBasedSampler = class {
	_ratio;
	_upperBound;
	constructor(ratio = 0) {
		this._ratio = this._normalize(ratio);
		this._upperBound = Math.floor(this._ratio * 4294967295);
	}
	shouldSample(context, traceId) {
		return { decision: isValidTraceId(traceId) && this._accumulate(traceId) < this._upperBound ? SamplingDecision.RECORD_AND_SAMPLED : SamplingDecision.NOT_RECORD };
	}
	toString() {
		return `TraceIdRatioBased{${this._ratio}}`;
	}
	_normalize(ratio) {
		if (typeof ratio !== "number" || isNaN(ratio)) return 0;
		return ratio >= 1 ? 1 : ratio <= 0 ? 0 : ratio;
	}
	_accumulate(traceId) {
		let accumulation = 0;
		for (let i = 0; i < 32; i += 8) {
			let part = 0;
			for (let j = 0; j < 8; j++) {
				const c = traceId.charCodeAt(i + j);
				const v = c < 58 ? c - 48 : c < 71 ? c - 55 : c - 87;
				part = part << 4 | v;
			}
			accumulation = (accumulation ^ part) >>> 0;
		}
		return accumulation;
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/config.js
var TracesSamplerValues;
(function(TracesSamplerValues) {
	TracesSamplerValues["AlwaysOff"] = "always_off";
	TracesSamplerValues["AlwaysOn"] = "always_on";
	TracesSamplerValues["ParentBasedAlwaysOff"] = "parentbased_always_off";
	TracesSamplerValues["ParentBasedAlwaysOn"] = "parentbased_always_on";
	TracesSamplerValues["ParentBasedTraceIdRatio"] = "parentbased_traceidratio";
	TracesSamplerValues["TraceIdRatio"] = "traceidratio";
})(TracesSamplerValues || (TracesSamplerValues = {}));
var DEFAULT_RATIO = 1;
/**
* Load default configuration. For fields with primitive values, any user-provided
* value will override the corresponding default value. For fields with
* non-primitive values (like `spanLimits`), the user-provided value will be
* used to extend the default value.
*/
function loadDefaultConfig() {
	return {
		sampler: buildSamplerFromEnv(),
		forceFlushTimeoutMillis: 3e4,
		generalLimits: {
			attributeValueLengthLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT") ?? Infinity,
			attributeCountLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_ATTRIBUTE_COUNT_LIMIT") ?? 128
		},
		spanLimits: {
			attributeValueLengthLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT") ?? Infinity,
			attributeCountLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT") ?? 128,
			linkCountLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_LINK_COUNT_LIMIT") ?? 128,
			eventCountLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_EVENT_COUNT_LIMIT") ?? 128,
			attributePerEventCountLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_ATTRIBUTE_PER_EVENT_COUNT_LIMIT") ?? 128,
			attributePerLinkCountLimit: /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_ATTRIBUTE_PER_LINK_COUNT_LIMIT") ?? 128
		}
	};
}
/**
* Based on environment, builds a sampler, complies with specification.
*/
function buildSamplerFromEnv() {
	const sampler = /* @__PURE__ */ getStringFromEnv("OTEL_TRACES_SAMPLER") ?? TracesSamplerValues.ParentBasedAlwaysOn;
	switch (sampler) {
		case TracesSamplerValues.AlwaysOn: return new AlwaysOnSampler();
		case TracesSamplerValues.AlwaysOff: return new AlwaysOffSampler();
		case TracesSamplerValues.ParentBasedAlwaysOn: return new ParentBasedSampler({ root: new AlwaysOnSampler() });
		case TracesSamplerValues.ParentBasedAlwaysOff: return new ParentBasedSampler({ root: new AlwaysOffSampler() });
		case TracesSamplerValues.TraceIdRatio: return new TraceIdRatioBasedSampler(getSamplerProbabilityFromEnv());
		case TracesSamplerValues.ParentBasedTraceIdRatio: return new ParentBasedSampler({ root: new TraceIdRatioBasedSampler(getSamplerProbabilityFromEnv()) });
		default:
			diag.error(`OTEL_TRACES_SAMPLER value "${sampler}" invalid, defaulting to "${TracesSamplerValues.ParentBasedAlwaysOn}".`);
			return new ParentBasedSampler({ root: new AlwaysOnSampler() });
	}
}
function getSamplerProbabilityFromEnv() {
	const probability = /* @__PURE__ */ getNumberFromEnv("OTEL_TRACES_SAMPLER_ARG");
	if (probability == null) {
		diag.error(`OTEL_TRACES_SAMPLER_ARG is blank, defaulting to ${DEFAULT_RATIO}.`);
		return DEFAULT_RATIO;
	}
	if (probability < 0 || probability > 1) {
		diag.error(`OTEL_TRACES_SAMPLER_ARG=${probability} was given, but it is out of range ([0..1]), defaulting to ${DEFAULT_RATIO}.`);
		return DEFAULT_RATIO;
	}
	return probability;
}
/**
* Function to merge Default configuration (as specified in './config') with
* user provided configurations.
*/
function mergeConfig(userConfig) {
	const perInstanceDefaults = { sampler: buildSamplerFromEnv() };
	const DEFAULT_CONFIG = loadDefaultConfig();
	const target = Object.assign({}, DEFAULT_CONFIG, perInstanceDefaults, userConfig);
	target.generalLimits = Object.assign({}, DEFAULT_CONFIG.generalLimits, userConfig.generalLimits || {});
	target.spanLimits = Object.assign({}, DEFAULT_CONFIG.spanLimits, userConfig.spanLimits || {});
	return target;
}
/**
* When general limits are provided and model specific limits are not,
* configures the model specific limits by using the values from the general ones.
* @param userConfig User provided tracer configuration
*/
function reconfigureLimits(userConfig) {
	const spanLimits = Object.assign({}, userConfig.spanLimits);
	/**
	* Reassign span attribute count limit to use first non null value defined by user or use default value
	*/
	spanLimits.attributeCountLimit = userConfig.spanLimits?.attributeCountLimit ?? userConfig.generalLimits?.attributeCountLimit ?? /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT") ?? /* @__PURE__ */ getNumberFromEnv("OTEL_ATTRIBUTE_COUNT_LIMIT") ?? 128;
	/**
	* Reassign span attribute value length limit to use first non null value defined by user or use default value
	*/
	spanLimits.attributeValueLengthLimit = userConfig.spanLimits?.attributeValueLengthLimit ?? userConfig.generalLimits?.attributeValueLengthLimit ?? /* @__PURE__ */ getNumberFromEnv("OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT") ?? /* @__PURE__ */ getNumberFromEnv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT") ?? Infinity;
	return Object.assign({}, userConfig, { spanLimits });
}
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/export/BatchSpanProcessorBase.js
/**
* Implementation of the {@link SpanProcessor} that batches spans exported by
* the SDK then pushes them to the exporter pipeline.
*/
var BatchSpanProcessorBase = class {
	_maxExportBatchSize;
	_maxQueueSize;
	_scheduledDelayMillis;
	_exportTimeoutMillis;
	_exporter;
	_isExporting = false;
	_finishedSpans = [];
	_timer;
	_shutdownOnce;
	_droppedSpansCount = 0;
	constructor(exporter, config) {
		this._exporter = exporter;
		this._maxExportBatchSize = typeof config?.maxExportBatchSize === "number" ? config.maxExportBatchSize : /* @__PURE__ */ getNumberFromEnv("OTEL_BSP_MAX_EXPORT_BATCH_SIZE") ?? 512;
		this._maxQueueSize = typeof config?.maxQueueSize === "number" ? config.maxQueueSize : /* @__PURE__ */ getNumberFromEnv("OTEL_BSP_MAX_QUEUE_SIZE") ?? 2048;
		this._scheduledDelayMillis = typeof config?.scheduledDelayMillis === "number" ? config.scheduledDelayMillis : /* @__PURE__ */ getNumberFromEnv("OTEL_BSP_SCHEDULE_DELAY") ?? 5e3;
		this._exportTimeoutMillis = typeof config?.exportTimeoutMillis === "number" ? config.exportTimeoutMillis : /* @__PURE__ */ getNumberFromEnv("OTEL_BSP_EXPORT_TIMEOUT") ?? 3e4;
		this._shutdownOnce = new BindOnceFuture(this._shutdown, this);
		if (this._maxExportBatchSize > this._maxQueueSize) {
			diag.warn("BatchSpanProcessor: maxExportBatchSize must be smaller or equal to maxQueueSize, setting maxExportBatchSize to match maxQueueSize");
			this._maxExportBatchSize = this._maxQueueSize;
		}
	}
	forceFlush() {
		if (this._shutdownOnce.isCalled) return this._shutdownOnce.promise;
		return this._flushAll();
	}
	onStart(_span, _parentContext) {}
	onEnd(span) {
		if (this._shutdownOnce.isCalled) return;
		if ((span.spanContext().traceFlags & TraceFlags.SAMPLED) === 0) return;
		this._addToBuffer(span);
	}
	shutdown() {
		return this._shutdownOnce.call();
	}
	_shutdown() {
		return Promise.resolve().then(() => {
			return this.onShutdown();
		}).then(() => {
			return this._flushAll();
		}).then(() => {
			return this._exporter.shutdown();
		});
	}
	/** Add a span in the buffer. */
	_addToBuffer(span) {
		if (this._finishedSpans.length >= this._maxQueueSize) {
			if (this._droppedSpansCount === 0) diag.debug("maxQueueSize reached, dropping spans");
			this._droppedSpansCount++;
			return;
		}
		if (this._droppedSpansCount > 0) {
			diag.warn(`Dropped ${this._droppedSpansCount} spans because maxQueueSize reached`);
			this._droppedSpansCount = 0;
		}
		this._finishedSpans.push(span);
		this._maybeStartTimer();
	}
	/**
	* Send all spans to the exporter respecting the batch size limit
	* This function is used only on forceFlush or shutdown,
	* for all other cases _flush should be used
	* */
	_flushAll() {
		return new Promise((resolve, reject) => {
			const promises = [];
			const count = Math.ceil(this._finishedSpans.length / this._maxExportBatchSize);
			for (let i = 0, j = count; i < j; i++) promises.push(this._flushOneBatch());
			Promise.all(promises).then(() => {
				resolve();
			}).catch(reject);
		});
	}
	_flushOneBatch() {
		this._clearTimer();
		if (this._finishedSpans.length === 0) return Promise.resolve();
		return new Promise((resolve, reject) => {
			const timer = setTimeout(() => {
				reject(/* @__PURE__ */ new Error("Timeout"));
			}, this._exportTimeoutMillis);
			context.with(suppressTracing(context.active()), () => {
				let spans;
				if (this._finishedSpans.length <= this._maxExportBatchSize) {
					spans = this._finishedSpans;
					this._finishedSpans = [];
				} else spans = this._finishedSpans.splice(0, this._maxExportBatchSize);
				const doExport = () => this._exporter.export(spans, (result) => {
					clearTimeout(timer);
					if (result.code === ExportResultCode.SUCCESS) resolve();
					else reject(result.error ?? /* @__PURE__ */ new Error("BatchSpanProcessor: span export failed"));
				});
				let pendingResources = null;
				for (let i = 0, len = spans.length; i < len; i++) {
					const span = spans[i];
					if (span.resource.asyncAttributesPending && span.resource.waitForAsyncAttributes) {
						pendingResources ??= [];
						pendingResources.push(span.resource.waitForAsyncAttributes());
					}
				}
				if (pendingResources === null) doExport();
				else Promise.all(pendingResources).then(doExport, (err) => {
					globalErrorHandler(err);
					reject(err);
				});
			});
		});
	}
	_maybeStartTimer() {
		if (this._isExporting) return;
		const flush = () => {
			this._isExporting = true;
			this._flushOneBatch().finally(() => {
				this._isExporting = false;
				if (this._finishedSpans.length > 0) {
					this._clearTimer();
					this._maybeStartTimer();
				}
			}).catch((e) => {
				this._isExporting = false;
				globalErrorHandler(e);
			});
		};
		if (this._finishedSpans.length >= this._maxExportBatchSize) return flush();
		if (this._timer !== void 0) return;
		this._timer = setTimeout(() => flush(), this._scheduledDelayMillis);
		if (typeof this._timer !== "number") this._timer.unref();
	}
	_clearTimer() {
		if (this._timer !== void 0) {
			clearTimeout(this._timer);
			this._timer = void 0;
		}
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/platform/browser/export/BatchSpanProcessor.js
var BatchSpanProcessor = class extends BatchSpanProcessorBase {
	_visibilityChangeListener;
	_pageHideListener;
	constructor(_exporter, config) {
		super(_exporter, config);
		this.onInit(config);
	}
	onInit(config) {
		if (config?.disableAutoFlushOnDocumentHide !== true && typeof document !== "undefined") {
			this._visibilityChangeListener = () => {
				if (document.visibilityState === "hidden") this.forceFlush().catch((error) => {
					globalErrorHandler(error);
				});
			};
			this._pageHideListener = () => {
				this.forceFlush().catch((error) => {
					globalErrorHandler(error);
				});
			};
			document.addEventListener("visibilitychange", this._visibilityChangeListener);
			document.addEventListener("pagehide", this._pageHideListener);
		}
	}
	onShutdown() {
		if (typeof document !== "undefined") {
			if (this._visibilityChangeListener) document.removeEventListener("visibilitychange", this._visibilityChangeListener);
			if (this._pageHideListener) document.removeEventListener("pagehide", this._pageHideListener);
		}
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/platform/browser/RandomIdGenerator.js
var TRACE_ID_BYTES = 16;
var SPAN_ID_BYTES = 8;
var TRACE_BUFFER = new Uint8Array(TRACE_ID_BYTES);
var SPAN_BUFFER = new Uint8Array(SPAN_ID_BYTES);
var HEX = Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, "0"));
/**
* Fills buffer with random bytes, ensuring at least one is non-zero
* per W3C Trace Context spec.
*/
function randomFill(buf) {
	for (let i = 0; i < buf.length; i++) buf[i] = Math.random() * 256 >>> 0;
	for (let i = 0; i < buf.length; i++) if (buf[i] > 0) return;
	buf[buf.length - 1] = 1;
}
function toHex(buf) {
	let hex = "";
	for (let i = 0; i < buf.length; i++) hex += HEX[buf[i]];
	return hex;
}
var RandomIdGenerator = class {
	/**
	* Returns a random 16-byte trace ID formatted/encoded as a 32 lowercase hex
	* characters corresponding to 128 bits.
	*/
	generateTraceId() {
		randomFill(TRACE_BUFFER);
		return toHex(TRACE_BUFFER);
	}
	/**
	* Returns a random 8-byte span ID formatted/encoded as a 16 lowercase hex
	* characters corresponding to 64 bits.
	*/
	generateSpanId() {
		randomFill(SPAN_BUFFER);
		return toHex(SPAN_BUFFER);
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/semconv.js
/**
* Determines whether the span has a parent span, and if so, [whether it is a remote parent](https://opentelemetry.io/docs/specs/otel/trace/api/#isremote)
*
* @experimental This attribute is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*/
var ATTR_OTEL_SPAN_PARENT_ORIGIN = "otel.span.parent.origin";
/**
* The result value of the sampler for this span
*
* @experimental This attribute is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*/
var ATTR_OTEL_SPAN_SAMPLING_RESULT = "otel.span.sampling_result";
/**
* The number of created spans with `recording=true` for which the end operation has not been called yet.
*
* @experimental This metric is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*/
var METRIC_OTEL_SDK_SPAN_LIVE = "otel.sdk.span.live";
/**
* The number of created spans.
*
* @note Implementations **MUST** record this metric for all spans, even for non-recording ones.
*
* @experimental This metric is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*/
var METRIC_OTEL_SDK_SPAN_STARTED = "otel.sdk.span.started";
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/TracerMetrics.js
/**
* Generates `otel.sdk.span.*` metrics.
* https://opentelemetry.io/docs/specs/semconv/otel/sdk-metrics/#span-metrics
*/
var TracerMetrics = class {
	startedSpans;
	liveSpans;
	constructor(meter) {
		this.startedSpans = meter.createCounter(METRIC_OTEL_SDK_SPAN_STARTED, {
			unit: "{span}",
			description: "The number of created spans."
		});
		this.liveSpans = meter.createUpDownCounter(METRIC_OTEL_SDK_SPAN_LIVE, {
			unit: "{span}",
			description: "The number of currently live spans."
		});
	}
	startSpan(parentSpanCtx, samplingDecision) {
		const samplingDecisionStr = samplingDecisionToString(samplingDecision);
		this.startedSpans.add(1, {
			[ATTR_OTEL_SPAN_PARENT_ORIGIN]: parentOrigin(parentSpanCtx),
			[ATTR_OTEL_SPAN_SAMPLING_RESULT]: samplingDecisionStr
		});
		if (samplingDecision === SamplingDecision.NOT_RECORD) return () => {};
		const liveSpanAttributes = { [ATTR_OTEL_SPAN_SAMPLING_RESULT]: samplingDecisionStr };
		this.liveSpans.add(1, liveSpanAttributes);
		return () => {
			this.liveSpans.add(-1, liveSpanAttributes);
		};
	}
};
function parentOrigin(parentSpanContext) {
	if (!parentSpanContext) return "none";
	if (parentSpanContext.isRemote) return "remote";
	return "local";
}
function samplingDecisionToString(decision) {
	switch (decision) {
		case SamplingDecision.RECORD_AND_SAMPLED: return "RECORD_AND_SAMPLE";
		case SamplingDecision.RECORD: return "RECORD_ONLY";
		case SamplingDecision.NOT_RECORD: return "DROP";
	}
}
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/version.js
var VERSION = "2.7.1";
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/Tracer.js
/**
* This class represents a basic tracer.
*/
var Tracer = class {
	_sampler;
	_generalLimits;
	_spanLimits;
	_idGenerator;
	instrumentationScope;
	_resource;
	_spanProcessor;
	_tracerMetrics;
	/**
	* Constructs a new Tracer instance.
	*/
	constructor(instrumentationScope, config, resource, spanProcessor) {
		const localConfig = mergeConfig(config);
		this._sampler = localConfig.sampler;
		this._generalLimits = localConfig.generalLimits;
		this._spanLimits = localConfig.spanLimits;
		this._idGenerator = config.idGenerator || new RandomIdGenerator();
		this._resource = resource;
		this._spanProcessor = spanProcessor;
		this.instrumentationScope = instrumentationScope;
		const meter = localConfig.meterProvider ? localConfig.meterProvider.getMeter("@opentelemetry/sdk-trace", VERSION) : createNoopMeter();
		this._tracerMetrics = new TracerMetrics(meter);
	}
	/**
	* Starts a new Span or returns the default NoopSpan based on the sampling
	* decision.
	*/
	startSpan(name, options = {}, context$1 = context.active()) {
		if (options.root) context$1 = trace.deleteSpan(context$1);
		const parentSpan = trace.getSpan(context$1);
		if (isTracingSuppressed(context$1)) {
			diag.debug("Instrumentation suppressed, returning Noop Span");
			return trace.wrapSpanContext(INVALID_SPAN_CONTEXT);
		}
		const parentSpanContext = parentSpan?.spanContext();
		const spanId = this._idGenerator.generateSpanId();
		let validParentSpanContext;
		let traceId;
		let traceState;
		if (!parentSpanContext || !trace.isSpanContextValid(parentSpanContext)) traceId = this._idGenerator.generateTraceId();
		else {
			traceId = parentSpanContext.traceId;
			traceState = parentSpanContext.traceState;
			validParentSpanContext = parentSpanContext;
		}
		const spanKind = options.kind ?? SpanKind.INTERNAL;
		const links = (options.links ?? []).map((link) => {
			return {
				context: link.context,
				attributes: sanitizeAttributes(link.attributes)
			};
		});
		const attributes = sanitizeAttributes(options.attributes);
		const samplingResult = this._sampler.shouldSample(context$1, traceId, name, spanKind, attributes, links);
		const recordEndMetrics = this._tracerMetrics.startSpan(parentSpanContext, samplingResult.decision);
		traceState = samplingResult.traceState ?? traceState;
		const traceFlags = samplingResult.decision === SamplingDecision$1.RECORD_AND_SAMPLED ? TraceFlags.SAMPLED : TraceFlags.NONE;
		const spanContext = {
			traceId,
			spanId,
			traceFlags,
			traceState
		};
		if (samplingResult.decision === SamplingDecision$1.NOT_RECORD) {
			diag.debug("Recording is off, propagating context in a non-recording span");
			return trace.wrapSpanContext(spanContext);
		}
		const initAttributes = sanitizeAttributes(Object.assign(attributes, samplingResult.attributes));
		return new SpanImpl({
			resource: this._resource,
			scope: this.instrumentationScope,
			context: context$1,
			spanContext,
			name,
			kind: spanKind,
			links,
			parentSpanContext: validParentSpanContext,
			attributes: initAttributes,
			startTime: options.startTime,
			spanProcessor: this._spanProcessor,
			spanLimits: this._spanLimits,
			recordEndMetrics
		});
	}
	startActiveSpan(name, arg2, arg3, arg4) {
		let opts;
		let ctx;
		let fn;
		if (arguments.length < 2) return;
		else if (arguments.length === 2) fn = arg2;
		else if (arguments.length === 3) {
			opts = arg2;
			fn = arg3;
		} else {
			opts = arg2;
			ctx = arg3;
			fn = arg4;
		}
		const parentContext = ctx ?? context.active();
		const span = this.startSpan(name, opts, parentContext);
		const contextWithSpanSet = trace.setSpan(parentContext, span);
		return context.with(contextWithSpanSet, fn, void 0, span);
	}
	/** Returns the active {@link GeneralLimits}. */
	getGeneralLimits() {
		return this._generalLimits;
	}
	/** Returns the active {@link SpanLimits}. */
	getSpanLimits() {
		return this._spanLimits;
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/MultiSpanProcessor.js
/**
* Implementation of the {@link SpanProcessor} that simply forwards all
* received events to a list of {@link SpanProcessor}s.
*/
var MultiSpanProcessor = class {
	_spanProcessors;
	constructor(spanProcessors) {
		this._spanProcessors = spanProcessors;
	}
	forceFlush() {
		const promises = [];
		for (const spanProcessor of this._spanProcessors) promises.push(spanProcessor.forceFlush());
		return new Promise((resolve) => {
			Promise.all(promises).then(() => {
				resolve();
			}).catch((error) => {
				globalErrorHandler(error || /* @__PURE__ */ new Error("MultiSpanProcessor: forceFlush failed"));
				resolve();
			});
		});
	}
	onStart(span, context) {
		for (const spanProcessor of this._spanProcessors) spanProcessor.onStart(span, context);
	}
	onEnding(span) {
		for (const spanProcessor of this._spanProcessors) if (spanProcessor.onEnding) spanProcessor.onEnding(span);
	}
	onEnd(span) {
		for (const spanProcessor of this._spanProcessors) spanProcessor.onEnd(span);
	}
	shutdown() {
		const promises = [];
		for (const spanProcessor of this._spanProcessors) promises.push(spanProcessor.shutdown());
		return new Promise((resolve, reject) => {
			Promise.all(promises).then(() => {
				resolve();
			}, reject);
		});
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/BasicTracerProvider.js
var ForceFlushState;
(function(ForceFlushState) {
	ForceFlushState[ForceFlushState["resolved"] = 0] = "resolved";
	ForceFlushState[ForceFlushState["timeout"] = 1] = "timeout";
	ForceFlushState[ForceFlushState["error"] = 2] = "error";
	ForceFlushState[ForceFlushState["unresolved"] = 3] = "unresolved";
})(ForceFlushState || (ForceFlushState = {}));
/**
* This class represents a basic tracer provider which platform libraries can extend
*/
var BasicTracerProvider = class {
	_config;
	_tracers = /* @__PURE__ */ new Map();
	_resource;
	_activeSpanProcessor;
	constructor(config = {}) {
		const mergedConfig = merge({}, loadDefaultConfig(), reconfigureLimits(config));
		this._resource = mergedConfig.resource ?? defaultResource();
		this._config = Object.assign({}, mergedConfig, { resource: this._resource });
		const spanProcessors = [];
		if (config.spanProcessors?.length) spanProcessors.push(...config.spanProcessors);
		this._activeSpanProcessor = new MultiSpanProcessor(spanProcessors);
	}
	getTracer(name, version, options) {
		const key = `${name}@${version || ""}:${options?.schemaUrl || ""}`;
		if (!this._tracers.has(key)) this._tracers.set(key, new Tracer({
			name,
			version,
			schemaUrl: options?.schemaUrl
		}, this._config, this._resource, this._activeSpanProcessor));
		return this._tracers.get(key);
	}
	forceFlush() {
		const timeout = this._config.forceFlushTimeoutMillis;
		const promises = this._activeSpanProcessor["_spanProcessors"].map((spanProcessor) => {
			return new Promise((resolve) => {
				let state;
				const timeoutInterval = setTimeout(() => {
					resolve(/* @__PURE__ */ new Error(`Span processor did not completed within timeout period of ${timeout} ms`));
					state = ForceFlushState.timeout;
				}, timeout);
				spanProcessor.forceFlush().then(() => {
					clearTimeout(timeoutInterval);
					if (state !== ForceFlushState.timeout) {
						state = ForceFlushState.resolved;
						resolve(state);
					}
				}).catch((error) => {
					clearTimeout(timeoutInterval);
					state = ForceFlushState.error;
					resolve(error);
				});
			});
		});
		return new Promise((resolve, reject) => {
			Promise.all(promises).then((results) => {
				const errors = results.filter((result) => result !== ForceFlushState.resolved);
				if (errors.length > 0) reject(errors);
				else resolve();
			}).catch((error) => reject([error]));
		});
	}
	shutdown() {
		return this._activeSpanProcessor.shutdown();
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/export/ConsoleSpanExporter.js
/**
* This is implementation of {@link SpanExporter} that prints spans to the
* console. This class can be used for diagnostic purposes.
*
* NOTE: This {@link SpanExporter} is intended for diagnostics use only, output rendered to the console may change at any time.
*/
var ConsoleSpanExporter = class {
	/**
	* Export spans.
	* @param spans
	* @param resultCallback
	*/
	export(spans, resultCallback) {
		return this._sendSpans(spans, resultCallback);
	}
	/**
	* Shutdown the exporter.
	*/
	shutdown() {
		this._sendSpans([]);
		return this.forceFlush();
	}
	/**
	* Exports any pending spans in exporter
	*/
	forceFlush() {
		return Promise.resolve();
	}
	/**
	* converts span info into more readable format
	* @param span
	*/
	_exportInfo(span) {
		return {
			resource: { attributes: span.resource.attributes },
			instrumentationScope: span.instrumentationScope,
			traceId: span.spanContext().traceId,
			parentSpanContext: span.parentSpanContext,
			traceState: span.spanContext().traceState?.serialize(),
			name: span.name,
			id: span.spanContext().spanId,
			kind: span.kind,
			timestamp: hrTimeToMicroseconds(span.startTime),
			duration: hrTimeToMicroseconds(span.duration),
			attributes: span.attributes,
			status: span.status,
			events: span.events,
			links: span.links
		};
	}
	/**
	* Showing spans in console
	* @param spans
	* @param done
	*/
	_sendSpans(spans, done) {
		for (const span of spans) console.dir(this._exportInfo(span), { depth: 3 });
		if (done) return done({ code: ExportResultCode.SUCCESS });
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/export/InMemorySpanExporter.js
/**
* This class can be used for testing purposes. It stores the exported spans
* in a list in memory that can be retrieved using the `getFinishedSpans()`
* method.
*/
var InMemorySpanExporter = class {
	_finishedSpans = [];
	/**
	* Indicates if the exporter has been "shutdown."
	* When false, exported spans will not be stored in-memory.
	*/
	_stopped = false;
	export(spans, resultCallback) {
		if (this._stopped) return resultCallback({
			code: ExportResultCode.FAILED,
			error: /* @__PURE__ */ new Error("Exporter has been stopped")
		});
		this._finishedSpans.push(...spans);
		setTimeout(() => resultCallback({ code: ExportResultCode.SUCCESS }), 0);
	}
	shutdown() {
		this._stopped = true;
		this._finishedSpans = [];
		return this.forceFlush();
	}
	/**
	* Exports any pending spans in the exporter
	*/
	forceFlush() {
		return Promise.resolve();
	}
	reset() {
		this._finishedSpans = [];
	}
	getFinishedSpans() {
		return this._finishedSpans;
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/export/SimpleSpanProcessor.js
/**
* An implementation of the {@link SpanProcessor} that converts the {@link Span}
* to {@link ReadableSpan} and passes it to the configured exporter.
*
* Only spans that are sampled are converted.
*
* NOTE: This {@link SpanProcessor} exports every ended span individually instead of batching spans together, which causes significant performance overhead with most exporters. For production use, please consider using the {@link BatchSpanProcessor} instead.
*/
var SimpleSpanProcessor = class {
	_exporter;
	_shutdownOnce;
	_pendingExports;
	constructor(exporter) {
		this._exporter = exporter;
		this._shutdownOnce = new BindOnceFuture(this._shutdown, this);
		this._pendingExports = /* @__PURE__ */ new Set();
	}
	async forceFlush() {
		await Promise.all(Array.from(this._pendingExports));
		if (this._exporter.forceFlush) await this._exporter.forceFlush();
	}
	onStart(_span, _parentContext) {}
	onEnd(span) {
		if (this._shutdownOnce.isCalled) return;
		if ((span.spanContext().traceFlags & TraceFlags.SAMPLED) === 0) return;
		const pendingExport = this._doExport(span).catch((err) => globalErrorHandler(err));
		this._pendingExports.add(pendingExport);
		pendingExport.finally(() => this._pendingExports.delete(pendingExport));
	}
	async _doExport(span) {
		if (span.resource.asyncAttributesPending) await span.resource.waitForAsyncAttributes?.();
		const result = await internal._export(this._exporter, [span]);
		if (result.code !== ExportResultCode.SUCCESS) throw result.error ?? /* @__PURE__ */ new Error(`SimpleSpanProcessor: span export failed (status ${result})`);
	}
	shutdown() {
		return this._shutdownOnce.call();
	}
	_shutdown() {
		return this._exporter.shutdown();
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-base/build/esm/export/NoopSpanProcessor.js
/** No-op implementation of SpanProcessor */
var NoopSpanProcessor = class {
	onStart(_span, _context) {}
	onEnd(_span) {}
	shutdown() {
		return Promise.resolve();
	}
	forceFlush() {
		return Promise.resolve();
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-web/build/esm/StackContextManager.js
/**
* Stack Context Manager for managing the state in web
* it doesn't fully support the async calls though
*/
var StackContextManager = class {
	/**
	* whether the context manager is enabled or not
	*/
	_enabled = false;
	/**
	* Keeps the reference to current context
	*/
	_currentContext = ROOT_CONTEXT;
	/**
	*
	* @param context
	* @param target Function to be executed within the context
	*/
	_bindFunction(context = ROOT_CONTEXT, target) {
		const manager = this;
		const contextWrapper = function(...args) {
			return manager.with(context, () => target.apply(this, args));
		};
		Object.defineProperty(contextWrapper, "length", {
			enumerable: false,
			configurable: true,
			writable: false,
			value: target.length
		});
		return contextWrapper;
	}
	/**
	* Returns the active context
	*/
	active() {
		return this._currentContext;
	}
	/**
	* Binds a the certain context or the active one to the target function and then returns the target
	* @param context A context (span) to be bind to target
	* @param target a function or event emitter. When target or one of its callbacks is called,
	*  the provided context will be used as the active context for the duration of the call.
	*/
	bind(context, target) {
		if (context === void 0) context = this.active();
		if (typeof target === "function") return this._bindFunction(context, target);
		return target;
	}
	/**
	* Disable the context manager (clears the current context)
	*/
	disable() {
		this._currentContext = ROOT_CONTEXT;
		this._enabled = false;
		return this;
	}
	/**
	* Enables the context manager and creates a default(root) context
	*/
	enable() {
		if (this._enabled) return this;
		this._enabled = true;
		this._currentContext = ROOT_CONTEXT;
		return this;
	}
	/**
	* Calls the callback function [fn] with the provided [context]. If [context] is undefined then it will use the window.
	* The context will be set as active
	* @param context
	* @param fn Callback function
	* @param thisArg optional receiver to be used for calling fn
	* @param args optional arguments forwarded to fn
	*/
	with(context, fn, thisArg, ...args) {
		const previousContext = this._currentContext;
		this._currentContext = context || ROOT_CONTEXT;
		try {
			return fn.call(thisArg, ...args);
		} finally {
			this._currentContext = previousContext;
		}
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-web/build/esm/WebTracerProvider.js
function setupContextManager(contextManager) {
	if (contextManager === null) return;
	if (contextManager === void 0) {
		const defaultContextManager = new StackContextManager();
		defaultContextManager.enable();
		context.setGlobalContextManager(defaultContextManager);
		return;
	}
	contextManager.enable();
	context.setGlobalContextManager(contextManager);
}
function setupPropagator(propagator) {
	if (propagator === null) return;
	if (propagator === void 0) {
		propagation.setGlobalPropagator(new CompositePropagator({ propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()] }));
		return;
	}
	propagation.setGlobalPropagator(propagator);
}
/**
* This class represents a web tracer with {@link StackContextManager}
*/
var WebTracerProvider = class extends BasicTracerProvider {
	/**
	* Constructs a new Tracer instance.
	* @param config Web Tracer config
	*/
	constructor(config = {}) {
		super(config);
	}
	/**
	* Register this TracerProvider for use with the OpenTelemetry API.
	* Undefined values may be replaced with defaults, and
	* null values will be skipped.
	*
	* @param config Configuration object for SDK registration
	*/
	register(config = {}) {
		trace.setGlobalTracerProvider(this);
		setupPropagator(config.propagator);
		setupContextManager(config.contextManager);
	}
};
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-web/build/esm/enums/PerformanceTimingNames.js
var PerformanceTimingNames;
(function(PerformanceTimingNames) {
	PerformanceTimingNames["CONNECT_END"] = "connectEnd";
	PerformanceTimingNames["CONNECT_START"] = "connectStart";
	PerformanceTimingNames["DECODED_BODY_SIZE"] = "decodedBodySize";
	PerformanceTimingNames["DOM_COMPLETE"] = "domComplete";
	PerformanceTimingNames["DOM_CONTENT_LOADED_EVENT_END"] = "domContentLoadedEventEnd";
	PerformanceTimingNames["DOM_CONTENT_LOADED_EVENT_START"] = "domContentLoadedEventStart";
	PerformanceTimingNames["DOM_INTERACTIVE"] = "domInteractive";
	PerformanceTimingNames["DOMAIN_LOOKUP_END"] = "domainLookupEnd";
	PerformanceTimingNames["DOMAIN_LOOKUP_START"] = "domainLookupStart";
	PerformanceTimingNames["ENCODED_BODY_SIZE"] = "encodedBodySize";
	PerformanceTimingNames["FETCH_START"] = "fetchStart";
	PerformanceTimingNames["LOAD_EVENT_END"] = "loadEventEnd";
	PerformanceTimingNames["LOAD_EVENT_START"] = "loadEventStart";
	PerformanceTimingNames["NAVIGATION_START"] = "navigationStart";
	PerformanceTimingNames["REDIRECT_END"] = "redirectEnd";
	PerformanceTimingNames["REDIRECT_START"] = "redirectStart";
	PerformanceTimingNames["REQUEST_START"] = "requestStart";
	PerformanceTimingNames["RESPONSE_END"] = "responseEnd";
	PerformanceTimingNames["RESPONSE_START"] = "responseStart";
	PerformanceTimingNames["SECURE_CONNECTION_START"] = "secureConnectionStart";
	PerformanceTimingNames["START_TIME"] = "startTime";
	PerformanceTimingNames["UNLOAD_EVENT_END"] = "unloadEventEnd";
	PerformanceTimingNames["UNLOAD_EVENT_START"] = "unloadEventStart";
})(PerformanceTimingNames || (PerformanceTimingNames = {}));
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-web/build/esm/semconv.js
/**
* Deprecated, use `http.response.header.<key>` instead.
*
* @example 3495
*
* @experimental This attribute is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*
* @deprecated Replaced by `http.response.header.<key>`.
*/
var ATTR_HTTP_RESPONSE_CONTENT_LENGTH = "http.response_content_length";
/**
* Deprecated, use `http.response.body.size` instead.
*
* @example 5493
*
* @experimental This attribute is experimental and is subject to breaking changes in minor releases of `@opentelemetry/semantic-conventions`.
*
* @deprecated Replace by `http.response.body.size`.
*/
var ATTR_HTTP_RESPONSE_CONTENT_LENGTH_UNCOMPRESSED = "http.response_content_length_uncompressed";
//#endregion
//#region node_modules/@opentelemetry/sdk-trace-web/build/esm/utils.js
var urlNormalizingAnchor;
function getUrlNormalizingAnchor() {
	if (!urlNormalizingAnchor) urlNormalizingAnchor = document.createElement("a");
	return urlNormalizingAnchor;
}
/**
* Helper function to be able to use enum as typed key in type and in interface when using forEach
* @param obj
* @param key
*/
function hasKey(obj, key) {
	return key in obj;
}
/**
* Helper function for starting an event on span based on {@link PerformanceEntries}
* @param span
* @param performanceName name of performance entry for time start
* @param entries
* @param ignoreZeros
*/
function addSpanNetworkEvent(span, performanceName, entries, ignoreZeros = true) {
	if (hasKey(entries, performanceName) && typeof entries[performanceName] === "number" && !(ignoreZeros && entries[performanceName] === 0)) return span.addEvent(performanceName, entries[performanceName]);
}
/**
* Helper function for adding network events and content length attributes.
*/
function addSpanNetworkEvents(span, resource, ignoreNetworkEvents = false, ignoreZeros, skipOldSemconvContentLengthAttrs) {
	if (ignoreZeros === void 0) ignoreZeros = resource[PerformanceTimingNames.START_TIME] !== 0;
	if (!ignoreNetworkEvents) {
		addSpanNetworkEvent(span, PerformanceTimingNames.FETCH_START, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.DOMAIN_LOOKUP_START, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.DOMAIN_LOOKUP_END, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.CONNECT_START, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.SECURE_CONNECTION_START, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.CONNECT_END, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.REQUEST_START, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.RESPONSE_START, resource, ignoreZeros);
		addSpanNetworkEvent(span, PerformanceTimingNames.RESPONSE_END, resource, ignoreZeros);
	}
	if (!skipOldSemconvContentLengthAttrs) {
		const encodedLength = resource[PerformanceTimingNames.ENCODED_BODY_SIZE];
		if (encodedLength !== void 0) span.setAttribute(ATTR_HTTP_RESPONSE_CONTENT_LENGTH, encodedLength);
		const decodedLength = resource[PerformanceTimingNames.DECODED_BODY_SIZE];
		if (decodedLength !== void 0 && encodedLength !== decodedLength) span.setAttribute(ATTR_HTTP_RESPONSE_CONTENT_LENGTH_UNCOMPRESSED, decodedLength);
	}
}
/**
* sort resources by startTime
* @param filteredResources
*/
function sortResources(filteredResources) {
	return filteredResources.slice().sort((a, b) => {
		const valueA = a[PerformanceTimingNames.FETCH_START];
		const valueB = b[PerformanceTimingNames.FETCH_START];
		if (valueA > valueB) return 1;
		else if (valueA < valueB) return -1;
		return 0;
	});
}
/** Returns the origin if present (if in browser context). */
function getOrigin() {
	return typeof location !== "undefined" ? location.origin : void 0;
}
/**
* Get closest performance resource ignoring the resources that have been
* already used.
* @param spanUrl
* @param startTimeHR
* @param endTimeHR
* @param resources
* @param ignoredResources
* @param initiatorType
*/
function getResource(spanUrl, startTimeHR, endTimeHR, resources, ignoredResources = /* @__PURE__ */ new WeakSet(), initiatorType) {
	const parsedSpanUrl = parseUrl(spanUrl);
	spanUrl = parsedSpanUrl.toString();
	const filteredResources = filterResourcesForSpan(spanUrl, startTimeHR, endTimeHR, resources, ignoredResources, initiatorType);
	if (filteredResources.length === 0) return { mainRequest: void 0 };
	if (filteredResources.length === 1) return { mainRequest: filteredResources[0] };
	const sorted = sortResources(filteredResources);
	if (parsedSpanUrl.origin !== getOrigin() && sorted.length > 1) {
		let corsPreFlightRequest = sorted[0];
		let mainRequest = findMainRequest(sorted, corsPreFlightRequest[PerformanceTimingNames.RESPONSE_END], endTimeHR);
		const responseEnd = corsPreFlightRequest[PerformanceTimingNames.RESPONSE_END];
		if (mainRequest[PerformanceTimingNames.FETCH_START] < responseEnd) {
			mainRequest = corsPreFlightRequest;
			corsPreFlightRequest = void 0;
		}
		return {
			corsPreFlightRequest,
			mainRequest
		};
	} else return { mainRequest: filteredResources[0] };
}
/**
* Will find the main request skipping the cors pre flight requests
* @param resources
* @param corsPreFlightRequestEndTime
* @param spanEndTimeHR
*/
function findMainRequest(resources, corsPreFlightRequestEndTime, spanEndTimeHR) {
	const spanEndTime = hrTimeToNanoseconds(spanEndTimeHR);
	const minTime = hrTimeToNanoseconds(timeInputToHrTime(corsPreFlightRequestEndTime));
	let mainRequest = resources[1];
	let bestGap;
	const length = resources.length;
	for (let i = 1; i < length; i++) {
		const resource = resources[i];
		const resourceStartTime = hrTimeToNanoseconds(timeInputToHrTime(resource[PerformanceTimingNames.FETCH_START]));
		const currentGap = spanEndTime - hrTimeToNanoseconds(timeInputToHrTime(resource[PerformanceTimingNames.RESPONSE_END]));
		if (resourceStartTime >= minTime && (!bestGap || currentGap < bestGap)) {
			bestGap = currentGap;
			mainRequest = resource;
		}
	}
	return mainRequest;
}
/**
* Filter all resources that has started and finished according to span start time and end time.
*     It will return the closest resource to a start time
* @param spanUrl
* @param startTimeHR
* @param endTimeHR
* @param resources
* @param ignoredResources
*/
function filterResourcesForSpan(spanUrl, startTimeHR, endTimeHR, resources, ignoredResources, initiatorType) {
	const startTime = hrTimeToNanoseconds(startTimeHR);
	const endTime = hrTimeToNanoseconds(endTimeHR);
	let filteredResources = resources.filter((resource) => {
		const resourceStartTime = hrTimeToNanoseconds(timeInputToHrTime(resource[PerformanceTimingNames.FETCH_START]));
		const resourceEndTime = hrTimeToNanoseconds(timeInputToHrTime(resource[PerformanceTimingNames.RESPONSE_END]));
		return resource.initiatorType.toLowerCase() === (initiatorType || "xmlhttprequest") && resource.name === spanUrl && resourceStartTime >= startTime && resourceEndTime <= endTime;
	});
	if (filteredResources.length > 0) filteredResources = filteredResources.filter((resource) => {
		return !ignoredResources.has(resource);
	});
	return filteredResources;
}
/**
* Parses url using URL constructor or fallback to anchor element.
* @param url
*/
function parseUrl(url) {
	if (typeof URL === "function") return new URL(url, typeof document !== "undefined" ? document.baseURI : typeof location !== "undefined" ? location.href : void 0);
	const element = getUrlNormalizingAnchor();
	element.href = url;
	return element;
}
/**
* Parses url using URL constructor or fallback to anchor element and serialize
* it to a string.
*
* Performs the steps described in https://html.spec.whatwg.org/multipage/urls-and-fetching.html#parse-a-url
*
* @param url
*/
function normalizeUrl(url) {
	return parseUrl(url).href;
}
/**
* Get element XPath
* @param target - target element
* @param optimised - when id attribute of element is present the xpath can be
* simplified to contain id
*/
function getElementXPath(target, optimised) {
	if (target.nodeType === Node.DOCUMENT_NODE) return "/";
	const targetValue = getNodeValue(target, optimised);
	if (optimised && targetValue.indexOf("@id") > 0) return targetValue;
	let xpath = "";
	if (target.parentNode) xpath += getElementXPath(target.parentNode, optimised);
	xpath += targetValue;
	return xpath;
}
/**
* get node index within the siblings
* @param target
*/
function getNodeIndex(target) {
	if (!target.parentNode) return 0;
	const allowedTypes = [target.nodeType];
	if (target.nodeType === Node.CDATA_SECTION_NODE) allowedTypes.push(Node.TEXT_NODE);
	let elements = Array.from(target.parentNode.childNodes);
	elements = elements.filter((element) => {
		const localName = element.localName;
		return allowedTypes.indexOf(element.nodeType) >= 0 && localName === target.localName;
	});
	if (elements.length >= 1) return elements.indexOf(target) + 1;
	return 0;
}
/**
* get node value for xpath
* @param target
* @param optimised
*/
function getNodeValue(target, optimised) {
	const nodeType = target.nodeType;
	const index = getNodeIndex(target);
	let nodeValue = "";
	if (nodeType === Node.ELEMENT_NODE) {
		const id = target.getAttribute("id");
		if (optimised && id) return `//*[@id="${id}"]`;
		nodeValue = target.localName;
	} else if (nodeType === Node.TEXT_NODE || nodeType === Node.CDATA_SECTION_NODE) nodeValue = "text()";
	else if (nodeType === Node.COMMENT_NODE) nodeValue = "comment()";
	else return "";
	if (nodeValue && index > 1) return `/${nodeValue}[${index}]`;
	return `/${nodeValue}`;
}
/**
* Checks if trace headers should be propagated
* @param spanUrl
* @private
*/
function shouldPropagateTraceHeaders(spanUrl, propagateTraceHeaderCorsUrls) {
	let propagateTraceHeaderUrls = propagateTraceHeaderCorsUrls || [];
	if (typeof propagateTraceHeaderUrls === "string" || propagateTraceHeaderUrls instanceof RegExp) propagateTraceHeaderUrls = [propagateTraceHeaderUrls];
	if (parseUrl(spanUrl).origin === getOrigin()) return true;
	else return propagateTraceHeaderUrls.some((propagateTraceHeaderUrl) => urlMatches(spanUrl, propagateTraceHeaderUrl));
}
//#endregion
export { AlwaysOffSampler, AlwaysOnSampler, BasicTracerProvider, BatchSpanProcessor, ConsoleSpanExporter, InMemorySpanExporter, NoopSpanProcessor, ParentBasedSampler, PerformanceTimingNames, RandomIdGenerator, SamplingDecision, SimpleSpanProcessor, StackContextManager, TraceIdRatioBasedSampler, WebTracerProvider, addSpanNetworkEvent, addSpanNetworkEvents, getElementXPath, getResource, hasKey, normalizeUrl, parseUrl, shouldPropagateTraceHeaders, sortResources };

//# sourceMappingURL=@opentelemetry_sdk-trace-web.js.map