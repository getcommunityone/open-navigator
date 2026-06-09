import { a as diag } from "./esm-DubyGMwv.js";
import { b as getStringFromEnv, v as SDK_INFO } from "./esm-CkK5VpJQ.js";
import { Cn as ATTR_TELEMETRY_SDK_NAME, Sn as ATTR_TELEMETRY_SDK_LANGUAGE, hn as ATTR_SERVICE_NAME, wn as ATTR_TELEMETRY_SDK_VERSION } from "./esm-Cg4aCtoK.js";
//#region node_modules/@opentelemetry/resources/build/esm/default-service-name.js
var serviceName;
/**
* Returns the default service name for OpenTelemetry resources.
* In Node.js environments, returns "unknown_service:<process.argv0>".
* In browser/edge environments, returns "unknown_service".
*/
function defaultServiceName() {
	if (serviceName === void 0) try {
		const argv0 = globalThis.process.argv0;
		serviceName = argv0 ? `unknown_service:${argv0}` : "unknown_service";
	} catch {
		serviceName = "unknown_service";
	}
	return serviceName;
}
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/utils.js
var isPromiseLike = (val) => {
	return val !== null && typeof val === "object" && typeof val.then === "function";
};
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/ResourceImpl.js
var ResourceImpl = class ResourceImpl {
	_rawAttributes;
	_asyncAttributesPending = false;
	_schemaUrl;
	_memoizedAttributes;
	static FromAttributeList(attributes, options) {
		const res = new ResourceImpl({}, options);
		res._rawAttributes = guardedRawAttributes(attributes);
		res._asyncAttributesPending = attributes.filter(([_, val]) => isPromiseLike(val)).length > 0;
		return res;
	}
	constructor(resource, options) {
		const attributes = resource.attributes ?? {};
		this._rawAttributes = Object.entries(attributes).map(([k, v]) => {
			if (isPromiseLike(v)) this._asyncAttributesPending = true;
			return [k, v];
		});
		this._rawAttributes = guardedRawAttributes(this._rawAttributes);
		this._schemaUrl = validateSchemaUrl(options?.schemaUrl);
	}
	get asyncAttributesPending() {
		return this._asyncAttributesPending;
	}
	async waitForAsyncAttributes() {
		if (!this.asyncAttributesPending) return;
		for (let i = 0; i < this._rawAttributes.length; i++) {
			const [k, v] = this._rawAttributes[i];
			this._rawAttributes[i] = [k, isPromiseLike(v) ? await v : v];
		}
		this._asyncAttributesPending = false;
	}
	get attributes() {
		if (this.asyncAttributesPending) diag.error("Accessing resource attributes before async attributes settled");
		if (this._memoizedAttributes) return this._memoizedAttributes;
		const attrs = {};
		for (const [k, v] of this._rawAttributes) {
			if (isPromiseLike(v)) {
				diag.debug(`Unsettled resource attribute ${k} skipped`);
				continue;
			}
			if (v != null) attrs[k] ??= v;
		}
		if (!this._asyncAttributesPending) this._memoizedAttributes = attrs;
		return attrs;
	}
	getRawAttributes() {
		return this._rawAttributes;
	}
	get schemaUrl() {
		return this._schemaUrl;
	}
	merge(resource) {
		if (resource == null) return this;
		const mergedSchemaUrl = mergeSchemaUrl(this, resource);
		const mergedOptions = mergedSchemaUrl ? { schemaUrl: mergedSchemaUrl } : void 0;
		return ResourceImpl.FromAttributeList([...resource.getRawAttributes(), ...this.getRawAttributes()], mergedOptions);
	}
};
function resourceFromAttributes(attributes, options) {
	return ResourceImpl.FromAttributeList(Object.entries(attributes), options);
}
function resourceFromDetectedResource(detectedResource, options) {
	return new ResourceImpl(detectedResource, options);
}
function emptyResource() {
	return resourceFromAttributes({});
}
function defaultResource() {
	return resourceFromAttributes({
		[ATTR_SERVICE_NAME]: defaultServiceName(),
		[ATTR_TELEMETRY_SDK_LANGUAGE]: SDK_INFO[ATTR_TELEMETRY_SDK_LANGUAGE],
		[ATTR_TELEMETRY_SDK_NAME]: SDK_INFO[ATTR_TELEMETRY_SDK_NAME],
		[ATTR_TELEMETRY_SDK_VERSION]: SDK_INFO[ATTR_TELEMETRY_SDK_VERSION]
	});
}
function guardedRawAttributes(attributes) {
	return attributes.map(([k, v]) => {
		if (isPromiseLike(v)) return [k, v.catch((err) => {
			diag.debug("promise rejection for resource attribute: %s - %s", k, err);
		})];
		return [k, v];
	});
}
function validateSchemaUrl(schemaUrl) {
	if (typeof schemaUrl === "string" || schemaUrl === void 0) return schemaUrl;
	diag.warn("Schema URL must be string or undefined, got %s. Schema URL will be ignored.", schemaUrl);
}
function mergeSchemaUrl(old, updating) {
	const oldSchemaUrl = old?.schemaUrl;
	const updatingSchemaUrl = updating?.schemaUrl;
	const isOldEmpty = oldSchemaUrl === void 0 || oldSchemaUrl === "";
	const isUpdatingEmpty = updatingSchemaUrl === void 0 || updatingSchemaUrl === "";
	if (isOldEmpty) return updatingSchemaUrl;
	if (isUpdatingEmpty) return oldSchemaUrl;
	if (oldSchemaUrl === updatingSchemaUrl) return oldSchemaUrl;
	diag.warn("Schema URL merge conflict: old resource has \"%s\", updating resource has \"%s\". Resulting resource will have undefined Schema URL.", oldSchemaUrl, updatingSchemaUrl);
}
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detect-resources.js
/**
* Runs all resource detectors and returns the results merged into a single Resource.
*
* @param config Configuration for resource detection
*/
var detectResources = (config = {}) => {
	return (config.detectors || []).map((d) => {
		try {
			const resource = resourceFromDetectedResource(d.detect(config));
			diag.debug(`${d.constructor.name} found resource.`, resource);
			return resource;
		} catch (e) {
			diag.debug(`${d.constructor.name} failed: ${e.message}`);
			return emptyResource();
		}
	}).reduce((acc, resource) => acc.merge(resource), emptyResource());
};
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detectors/EnvDetector.js
/**
* EnvDetector can be used to detect the presence of and create a Resource
* from the OTEL_RESOURCE_ATTRIBUTES environment variable.
*/
var EnvDetector = class {
	_MAX_LENGTH = 255;
	_COMMA_SEPARATOR = ",";
	_LABEL_KEY_VALUE_SPLITTER = "=";
	/**
	* Returns a {@link Resource} populated with attributes from the
	* OTEL_RESOURCE_ATTRIBUTES environment variable. Note this is an async
	* function to conform to the Detector interface.
	*
	* @param config The resource detection config
	*/
	detect(_config) {
		const attributes = {};
		const rawAttributes = /* @__PURE__ */ getStringFromEnv("OTEL_RESOURCE_ATTRIBUTES");
		const serviceName = /* @__PURE__ */ getStringFromEnv("OTEL_SERVICE_NAME");
		if (rawAttributes) try {
			const parsedAttributes = this._parseResourceAttributes(rawAttributes);
			Object.assign(attributes, parsedAttributes);
		} catch (e) {
			diag.debug(`EnvDetector failed: ${e instanceof Error ? e.message : e}`);
		}
		if (serviceName) attributes[ATTR_SERVICE_NAME] = serviceName;
		return { attributes };
	}
	/**
	* Creates an attribute map from the OTEL_RESOURCE_ATTRIBUTES environment
	* variable.
	*
	* OTEL_RESOURCE_ATTRIBUTES: A comma-separated list of attributes in the
	* format "key1=value1,key2=value2". The ',' and '=' characters in keys
	* and values MUST be percent-encoded. Other characters MAY be percent-encoded.
	*
	* Per the spec, on any error (e.g., decoding failure), the entire environment
	* variable value is discarded.
	*
	* @param rawEnvAttributes The resource attributes as a comma-separated list
	* of key/value pairs.
	* @returns The parsed resource attributes.
	* @throws Error if parsing fails (caller handles by discarding all attributes)
	*/
	_parseResourceAttributes(rawEnvAttributes) {
		if (!rawEnvAttributes) return {};
		const attributes = {};
		const rawAttributes = rawEnvAttributes.split(this._COMMA_SEPARATOR).filter((attr) => attr.trim() !== "");
		for (const rawAttribute of rawAttributes) {
			const keyValuePair = rawAttribute.split(this._LABEL_KEY_VALUE_SPLITTER);
			if (keyValuePair.length !== 2) throw new Error(`Invalid format for OTEL_RESOURCE_ATTRIBUTES: "${rawAttribute}". Expected format: key=value. The ',' and '=' characters must be percent-encoded in keys and values.`);
			const [rawKey, rawValue] = keyValuePair;
			const key = rawKey.trim();
			const value = rawValue.trim();
			if (key.length === 0) throw new Error(`Invalid OTEL_RESOURCE_ATTRIBUTES: empty attribute key in "${rawAttribute}".`);
			let decodedKey;
			let decodedValue;
			try {
				decodedKey = decodeURIComponent(key);
				decodedValue = decodeURIComponent(value);
			} catch (e) {
				throw new Error(`Failed to percent-decode OTEL_RESOURCE_ATTRIBUTES entry "${rawAttribute}": ${e instanceof Error ? e.message : e}`);
			}
			if (decodedKey.length > this._MAX_LENGTH) throw new Error(`Attribute key exceeds the maximum length of ${this._MAX_LENGTH} characters: "${decodedKey}".`);
			if (decodedValue.length > this._MAX_LENGTH) throw new Error(`Attribute value exceeds the maximum length of ${this._MAX_LENGTH} characters for key "${decodedKey}".`);
			attributes[decodedKey] = decodedValue;
		}
		return attributes;
	}
};
var envDetector = new EnvDetector();
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detectors/NoopDetector.js
var NoopDetector = class {
	detect() {
		return { attributes: {} };
	}
};
var noopDetector = new NoopDetector();
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detectors/platform/browser/HostDetector.js
var hostDetector = noopDetector;
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detectors/platform/browser/OSDetector.js
var osDetector = noopDetector;
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detectors/platform/browser/ProcessDetector.js
var processDetector = noopDetector;
//#endregion
//#region node_modules/@opentelemetry/resources/build/esm/detectors/platform/browser/ServiceInstanceIdDetector.js
/**
* @experimental
*/
var serviceInstanceIdDetector = noopDetector;
//#endregion
export { envDetector as a, emptyResource as c, hostDetector as i, resourceFromAttributes as l, processDetector as n, detectResources as o, osDetector as r, defaultResource as s, serviceInstanceIdDetector as t, defaultServiceName as u };

//# sourceMappingURL=esm-BqDCjizk.js.map