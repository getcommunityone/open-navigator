import { n as __esmMin, r as __exportAll, t as __commonJSMin } from "./chunk-_TIqcEvS.js";
import { t as require_react } from "./react.js";
import { t as require_prop_types } from "./prop-types-WOmwsC-r.js";
//#region node_modules/deepmerge/dist/cjs.js
var require_cjs = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var isMergeableObject = function isMergeableObject(value) {
		return isNonNullObject(value) && !isSpecial(value);
	};
	function isNonNullObject(value) {
		return !!value && typeof value === "object";
	}
	function isSpecial(value) {
		var stringValue = Object.prototype.toString.call(value);
		return stringValue === "[object RegExp]" || stringValue === "[object Date]" || isReactElement(value);
	}
	var REACT_ELEMENT_TYPE = typeof Symbol === "function" && Symbol.for ? Symbol.for("react.element") : 60103;
	function isReactElement(value) {
		return value.$$typeof === REACT_ELEMENT_TYPE;
	}
	function emptyTarget(val) {
		return Array.isArray(val) ? [] : {};
	}
	function cloneUnlessOtherwiseSpecified(value, options) {
		return options.clone !== false && options.isMergeableObject(value) ? deepmerge(emptyTarget(value), value, options) : value;
	}
	function defaultArrayMerge(target, source, options) {
		return target.concat(source).map(function(element) {
			return cloneUnlessOtherwiseSpecified(element, options);
		});
	}
	function getMergeFunction(key, options) {
		if (!options.customMerge) return deepmerge;
		var customMerge = options.customMerge(key);
		return typeof customMerge === "function" ? customMerge : deepmerge;
	}
	function getEnumerableOwnPropertySymbols(target) {
		return Object.getOwnPropertySymbols ? Object.getOwnPropertySymbols(target).filter(function(symbol) {
			return Object.propertyIsEnumerable.call(target, symbol);
		}) : [];
	}
	function getKeys(target) {
		return Object.keys(target).concat(getEnumerableOwnPropertySymbols(target));
	}
	function propertyIsOnObject(object, property) {
		try {
			return property in object;
		} catch (_) {
			return false;
		}
	}
	function propertyIsUnsafe(target, key) {
		return propertyIsOnObject(target, key) && !(Object.hasOwnProperty.call(target, key) && Object.propertyIsEnumerable.call(target, key));
	}
	function mergeObject(target, source, options) {
		var destination = {};
		if (options.isMergeableObject(target)) getKeys(target).forEach(function(key) {
			destination[key] = cloneUnlessOtherwiseSpecified(target[key], options);
		});
		getKeys(source).forEach(function(key) {
			if (propertyIsUnsafe(target, key)) return;
			if (propertyIsOnObject(target, key) && options.isMergeableObject(source[key])) destination[key] = getMergeFunction(key, options)(target[key], source[key], options);
			else destination[key] = cloneUnlessOtherwiseSpecified(source[key], options);
		});
		return destination;
	}
	function deepmerge(target, source, options) {
		options = options || {};
		options.arrayMerge = options.arrayMerge || defaultArrayMerge;
		options.isMergeableObject = options.isMergeableObject || isMergeableObject;
		options.cloneUnlessOtherwiseSpecified = cloneUnlessOtherwiseSpecified;
		var sourceIsArray = Array.isArray(source);
		if (!(sourceIsArray === Array.isArray(target))) return cloneUnlessOtherwiseSpecified(source, options);
		else if (sourceIsArray) return options.arrayMerge(target, source, options);
		else return mergeObject(target, source, options);
	}
	deepmerge.all = function deepmergeAll(array, options) {
		if (!Array.isArray(array)) throw new Error("first argument should be an array");
		return array.reduce(function(prev, next) {
			return deepmerge(prev, next, options);
		}, {});
	};
	module.exports = deepmerge;
}));
//#endregion
//#region node_modules/react-player/node_modules/memoize-one/dist/memoize-one.esm.js
var memoize_one_esm_exports = /* @__PURE__ */ __exportAll({ default: () => memoizeOne });
function isEqual(first, second) {
	if (first === second) return true;
	if (safeIsNaN(first) && safeIsNaN(second)) return true;
	return false;
}
function areInputsEqual(newInputs, lastInputs) {
	if (newInputs.length !== lastInputs.length) return false;
	for (var i = 0; i < newInputs.length; i++) if (!isEqual(newInputs[i], lastInputs[i])) return false;
	return true;
}
function memoizeOne(resultFn, isEqual) {
	if (isEqual === void 0) isEqual = areInputsEqual;
	var lastThis;
	var lastArgs = [];
	var lastResult;
	var calledOnce = false;
	function memoized() {
		var newArgs = [];
		for (var _i = 0; _i < arguments.length; _i++) newArgs[_i] = arguments[_i];
		if (calledOnce && lastThis === this && isEqual(newArgs, lastArgs)) return lastResult;
		lastResult = resultFn.apply(this, newArgs);
		calledOnce = true;
		lastThis = this;
		lastArgs = newArgs;
		return lastResult;
	}
	return memoized;
}
var safeIsNaN;
var init_memoize_one_esm = __esmMin((() => {
	safeIsNaN = Number.isNaN || function ponyfill(value) {
		return typeof value === "number" && value !== value;
	};
}));
//#endregion
//#region node_modules/react-fast-compare/index.js
var require_react_fast_compare = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var hasElementType = typeof Element !== "undefined";
	var hasMap = typeof Map === "function";
	var hasSet = typeof Set === "function";
	var hasArrayBuffer = typeof ArrayBuffer === "function" && !!ArrayBuffer.isView;
	function equal(a, b) {
		if (a === b) return true;
		if (a && b && typeof a == "object" && typeof b == "object") {
			if (a.constructor !== b.constructor) return false;
			var length, i, keys;
			if (Array.isArray(a)) {
				length = a.length;
				if (length != b.length) return false;
				for (i = length; i-- !== 0;) if (!equal(a[i], b[i])) return false;
				return true;
			}
			var it;
			if (hasMap && a instanceof Map && b instanceof Map) {
				if (a.size !== b.size) return false;
				it = a.entries();
				while (!(i = it.next()).done) if (!b.has(i.value[0])) return false;
				it = a.entries();
				while (!(i = it.next()).done) if (!equal(i.value[1], b.get(i.value[0]))) return false;
				return true;
			}
			if (hasSet && a instanceof Set && b instanceof Set) {
				if (a.size !== b.size) return false;
				it = a.entries();
				while (!(i = it.next()).done) if (!b.has(i.value[0])) return false;
				return true;
			}
			if (hasArrayBuffer && ArrayBuffer.isView(a) && ArrayBuffer.isView(b)) {
				length = a.length;
				if (length != b.length) return false;
				for (i = length; i-- !== 0;) if (a[i] !== b[i]) return false;
				return true;
			}
			if (a.constructor === RegExp) return a.source === b.source && a.flags === b.flags;
			if (a.valueOf !== Object.prototype.valueOf && typeof a.valueOf === "function" && typeof b.valueOf === "function") return a.valueOf() === b.valueOf();
			if (a.toString !== Object.prototype.toString && typeof a.toString === "function" && typeof b.toString === "function") return a.toString() === b.toString();
			keys = Object.keys(a);
			length = keys.length;
			if (length !== Object.keys(b).length) return false;
			for (i = length; i-- !== 0;) if (!Object.prototype.hasOwnProperty.call(b, keys[i])) return false;
			if (hasElementType && a instanceof Element) return false;
			for (i = length; i-- !== 0;) {
				if ((keys[i] === "_owner" || keys[i] === "__v" || keys[i] === "__o") && a.$$typeof) continue;
				if (!equal(a[keys[i]], b[keys[i]])) return false;
			}
			return true;
		}
		return a !== a && b !== b;
	}
	module.exports = function isEqual(a, b) {
		try {
			return equal(a, b);
		} catch (error) {
			if ((error.message || "").match(/stack|recursion/i)) {
				console.warn("react-fast-compare cannot handle circular refs");
				return false;
			}
			throw error;
		}
	};
}));
//#endregion
//#region node_modules/react-player/lib/props.js
var require_props = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var __create = Object.create;
	var __defProp = Object.defineProperty;
	var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
	var __getOwnPropNames = Object.getOwnPropertyNames;
	var __getProtoOf = Object.getPrototypeOf;
	var __hasOwnProp = Object.prototype.hasOwnProperty;
	var __export = (target, all) => {
		for (var name in all) __defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	};
	var __copyProps = (to, from, except, desc) => {
		if (from && typeof from === "object" || typeof from === "function") {
			for (let key of __getOwnPropNames(from)) if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
				get: () => from[key],
				enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
			});
		}
		return to;
	};
	var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", {
		value: mod,
		enumerable: true
	}) : target, mod));
	var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
	var props_exports = {};
	__export(props_exports, {
		defaultProps: () => defaultProps,
		propTypes: () => propTypes
	});
	module.exports = __toCommonJS(props_exports);
	var { string, bool, number, array, oneOfType, shape, object, func, node } = __toESM(require_prop_types()).default;
	var propTypes = {
		url: oneOfType([
			string,
			array,
			object
		]),
		playing: bool,
		loop: bool,
		controls: bool,
		volume: number,
		muted: bool,
		playbackRate: number,
		width: oneOfType([string, number]),
		height: oneOfType([string, number]),
		style: object,
		progressInterval: number,
		playsinline: bool,
		pip: bool,
		stopOnUnmount: bool,
		light: oneOfType([
			bool,
			string,
			object
		]),
		playIcon: node,
		previewTabIndex: number,
		previewAriaLabel: string,
		fallback: node,
		oEmbedUrl: string,
		wrapper: oneOfType([
			string,
			func,
			shape({ render: func.isRequired })
		]),
		config: shape({
			soundcloud: shape({ options: object }),
			youtube: shape({
				playerVars: object,
				embedOptions: object,
				onUnstarted: func
			}),
			facebook: shape({
				appId: string,
				version: string,
				playerId: string,
				attributes: object
			}),
			dailymotion: shape({ params: object }),
			vimeo: shape({
				playerOptions: object,
				title: string
			}),
			mux: shape({
				attributes: object,
				version: string
			}),
			file: shape({
				attributes: object,
				tracks: array,
				forceVideo: bool,
				forceAudio: bool,
				forceHLS: bool,
				forceSafariHLS: bool,
				forceDisableHls: bool,
				forceDASH: bool,
				forceFLV: bool,
				hlsOptions: object,
				hlsVersion: string,
				dashVersion: string,
				flvVersion: string
			}),
			wistia: shape({
				options: object,
				playerId: string,
				customControls: array
			}),
			mixcloud: shape({ options: object }),
			twitch: shape({
				options: object,
				playerId: string
			}),
			vidyard: shape({ options: object })
		}),
		onReady: func,
		onStart: func,
		onPlay: func,
		onPause: func,
		onBuffer: func,
		onBufferEnd: func,
		onEnded: func,
		onError: func,
		onDuration: func,
		onSeek: func,
		onPlaybackRateChange: func,
		onPlaybackQualityChange: func,
		onProgress: func,
		onClickPreview: func,
		onEnablePIP: func,
		onDisablePIP: func
	};
	var noop = () => {};
	var defaultProps = {
		playing: false,
		loop: false,
		controls: false,
		volume: null,
		muted: false,
		playbackRate: 1,
		width: "640px",
		height: "360px",
		style: {},
		progressInterval: 1e3,
		playsinline: false,
		pip: false,
		stopOnUnmount: true,
		light: false,
		fallback: null,
		wrapper: "div",
		previewTabIndex: 0,
		previewAriaLabel: "",
		oEmbedUrl: "https://noembed.com/embed?url={url}",
		config: {
			soundcloud: { options: {
				visual: true,
				buying: false,
				liking: false,
				download: false,
				sharing: false,
				show_comments: false,
				show_playcount: false
			} },
			youtube: {
				playerVars: {
					playsinline: 1,
					showinfo: 0,
					rel: 0,
					iv_load_policy: 3,
					modestbranding: 1
				},
				embedOptions: {},
				onUnstarted: noop
			},
			facebook: {
				appId: "1309697205772819",
				version: "v3.3",
				playerId: null,
				attributes: {}
			},
			dailymotion: { params: {
				api: 1,
				"endscreen-enable": false
			} },
			vimeo: {
				playerOptions: {
					autopause: false,
					byline: false,
					portrait: false,
					title: false
				},
				title: null
			},
			mux: {
				attributes: {},
				version: "2"
			},
			file: {
				attributes: {},
				tracks: [],
				forceVideo: false,
				forceAudio: false,
				forceHLS: false,
				forceDASH: false,
				forceFLV: false,
				hlsOptions: {},
				hlsVersion: "1.1.4",
				dashVersion: "3.1.3",
				flvVersion: "1.5.0",
				forceDisableHls: false
			},
			wistia: {
				options: {},
				playerId: null,
				customControls: null
			},
			mixcloud: { options: { hide_cover: 1 } },
			twitch: {
				options: {},
				playerId: null
			},
			vidyard: { options: {} }
		},
		onReady: noop,
		onStart: noop,
		onPlay: noop,
		onPause: noop,
		onBuffer: noop,
		onBufferEnd: noop,
		onEnded: noop,
		onError: noop,
		onDuration: noop,
		onSeek: noop,
		onPlaybackRateChange: noop,
		onPlaybackQualityChange: noop,
		onProgress: noop,
		onClickPreview: noop,
		onEnablePIP: noop,
		onDisablePIP: noop
	};
}));
//#endregion
//#region node_modules/load-script/index.js
var require_load_script = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	module.exports = function load(src, opts, cb) {
		var head = document.head || document.getElementsByTagName("head")[0];
		var script = document.createElement("script");
		if (typeof opts === "function") {
			cb = opts;
			opts = {};
		}
		opts = opts || {};
		cb = cb || function() {};
		script.type = opts.type || "text/javascript";
		script.charset = opts.charset || "utf8";
		script.async = "async" in opts ? !!opts.async : true;
		script.src = src;
		if (opts.attrs) setAttributes(script, opts.attrs);
		if (opts.text) script.text = "" + opts.text;
		("onload" in script ? stdOnEnd : ieOnEnd)(script, cb);
		if (!script.onload) stdOnEnd(script, cb);
		head.appendChild(script);
	};
	function setAttributes(script, attrs) {
		for (var attr in attrs) script.setAttribute(attr, attrs[attr]);
	}
	function stdOnEnd(script, cb) {
		script.onload = function() {
			this.onerror = this.onload = null;
			cb(null, script);
		};
		script.onerror = function() {
			this.onerror = this.onload = null;
			cb(/* @__PURE__ */ new Error("Failed to load " + this.src), script);
		};
	}
	function ieOnEnd(script, cb) {
		script.onreadystatechange = function() {
			if (this.readyState != "complete" && this.readyState != "loaded") return;
			this.onreadystatechange = null;
			cb(null, script);
		};
	}
}));
//#endregion
//#region node_modules/react-player/lib/utils.js
var require_utils = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var __create = Object.create;
	var __defProp = Object.defineProperty;
	var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
	var __getOwnPropNames = Object.getOwnPropertyNames;
	var __getProtoOf = Object.getPrototypeOf;
	var __hasOwnProp = Object.prototype.hasOwnProperty;
	var __export = (target, all) => {
		for (var name in all) __defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	};
	var __copyProps = (to, from, except, desc) => {
		if (from && typeof from === "object" || typeof from === "function") {
			for (let key of __getOwnPropNames(from)) if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
				get: () => from[key],
				enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
			});
		}
		return to;
	};
	var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", {
		value: mod,
		enumerable: true
	}) : target, mod));
	var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
	var utils_exports = {};
	__export(utils_exports, {
		callPlayer: () => callPlayer,
		getConfig: () => getConfig,
		getSDK: () => getSDK,
		isBlobUrl: () => isBlobUrl,
		isMediaStream: () => isMediaStream,
		lazy: () => lazy,
		omit: () => omit,
		parseEndTime: () => parseEndTime,
		parseStartTime: () => parseStartTime,
		queryString: () => queryString,
		randomString: () => randomString,
		supportsWebKitPresentationMode: () => supportsWebKitPresentationMode
	});
	module.exports = __toCommonJS(utils_exports);
	var import_react = __toESM(require_react());
	var import_load_script = __toESM(require_load_script());
	var import_deepmerge = __toESM(require_cjs());
	var lazy = (componentImportFn) => import_react.default.lazy(async () => {
		const obj = await componentImportFn();
		return typeof obj.default === "function" ? obj : obj.default;
	});
	var MATCH_START_QUERY = /[?&#](?:start|t)=([0-9hms]+)/;
	var MATCH_END_QUERY = /[?&#]end=([0-9hms]+)/;
	var MATCH_START_STAMP = /(\d+)(h|m|s)/g;
	var MATCH_NUMERIC = /^\d+$/;
	function parseTimeParam(url, pattern) {
		if (url instanceof Array) return;
		const match = url.match(pattern);
		if (match) {
			const stamp = match[1];
			if (stamp.match(MATCH_START_STAMP)) return parseTimeString(stamp);
			if (MATCH_NUMERIC.test(stamp)) return parseInt(stamp);
		}
	}
	function parseTimeString(stamp) {
		let seconds = 0;
		let array = MATCH_START_STAMP.exec(stamp);
		while (array !== null) {
			const [, count, period] = array;
			if (period === "h") seconds += parseInt(count, 10) * 60 * 60;
			if (period === "m") seconds += parseInt(count, 10) * 60;
			if (period === "s") seconds += parseInt(count, 10);
			array = MATCH_START_STAMP.exec(stamp);
		}
		return seconds;
	}
	function parseStartTime(url) {
		return parseTimeParam(url, MATCH_START_QUERY);
	}
	function parseEndTime(url) {
		return parseTimeParam(url, MATCH_END_QUERY);
	}
	function randomString() {
		return Math.random().toString(36).substr(2, 5);
	}
	function queryString(object) {
		return Object.keys(object).map((key) => `${key}=${object[key]}`).join("&");
	}
	function getGlobal(key) {
		if (window[key]) return window[key];
		if (window.exports && window.exports[key]) return window.exports[key];
		if (window.module && window.module.exports && window.module.exports[key]) return window.module.exports[key];
		return null;
	}
	var requests = {};
	var getSDK = enableStubOn(function getSDK2(url, sdkGlobal, sdkReady = null, isLoaded = () => true, fetchScript = import_load_script.default) {
		const existingGlobal = getGlobal(sdkGlobal);
		if (existingGlobal && isLoaded(existingGlobal)) return Promise.resolve(existingGlobal);
		return new Promise((resolve, reject) => {
			if (requests[url]) {
				requests[url].push({
					resolve,
					reject
				});
				return;
			}
			requests[url] = [{
				resolve,
				reject
			}];
			const onLoaded = (sdk) => {
				requests[url].forEach((request) => request.resolve(sdk));
			};
			if (sdkReady) {
				const previousOnReady = window[sdkReady];
				window[sdkReady] = function() {
					if (previousOnReady) previousOnReady();
					onLoaded(getGlobal(sdkGlobal));
				};
			}
			fetchScript(url, (err) => {
				if (err) {
					requests[url].forEach((request) => request.reject(err));
					requests[url] = null;
				} else if (!sdkReady) onLoaded(getGlobal(sdkGlobal));
			});
		});
	});
	function getConfig(props, defaultProps) {
		return (0, import_deepmerge.default)(defaultProps.config, props.config);
	}
	function omit(object, ...arrays) {
		const omitKeys = [].concat(...arrays);
		const output = {};
		const keys = Object.keys(object);
		for (const key of keys) if (omitKeys.indexOf(key) === -1) output[key] = object[key];
		return output;
	}
	function callPlayer(method, ...args) {
		if (!this.player || !this.player[method]) {
			let message = `ReactPlayer: ${this.constructor.displayName} player could not call %c${method}%c \u2013 `;
			if (!this.player) message += "The player was not available";
			else if (!this.player[method]) message += "The method was not available";
			console.warn(message, "font-weight: bold", "");
			return null;
		}
		return this.player[method](...args);
	}
	function isMediaStream(url) {
		return typeof window !== "undefined" && typeof window.MediaStream !== "undefined" && url instanceof window.MediaStream;
	}
	function isBlobUrl(url) {
		return /^blob:/.test(url);
	}
	function supportsWebKitPresentationMode(video = document.createElement("video")) {
		const notMobile = /iPhone|iPod/.test(navigator.userAgent) === false;
		return video.webkitSupportsPresentationMode && typeof video.webkitSetPresentationMode === "function" && notMobile;
	}
	function enableStubOn(fn) {
		return fn;
	}
}));
//#endregion
//#region node_modules/react-player/lib/Player.js
var require_Player = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var __create = Object.create;
	var __defProp = Object.defineProperty;
	var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
	var __getOwnPropNames = Object.getOwnPropertyNames;
	var __getProtoOf = Object.getPrototypeOf;
	var __hasOwnProp = Object.prototype.hasOwnProperty;
	var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, {
		enumerable: true,
		configurable: true,
		writable: true,
		value
	}) : obj[key] = value;
	var __export = (target, all) => {
		for (var name in all) __defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	};
	var __copyProps = (to, from, except, desc) => {
		if (from && typeof from === "object" || typeof from === "function") {
			for (let key of __getOwnPropNames(from)) if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
				get: () => from[key],
				enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
			});
		}
		return to;
	};
	var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", {
		value: mod,
		enumerable: true
	}) : target, mod));
	var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
	var __publicField = (obj, key, value) => {
		__defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
		return value;
	};
	var Player_exports = {};
	__export(Player_exports, { default: () => Player });
	module.exports = __toCommonJS(Player_exports);
	var import_react = __toESM(require_react());
	var import_react_fast_compare = __toESM(require_react_fast_compare());
	var import_props = require_props();
	var import_utils = require_utils();
	var SEEK_ON_PLAY_EXPIRY = 5e3;
	var Player = class extends import_react.Component {
		constructor() {
			super(...arguments);
			__publicField(this, "mounted", false);
			__publicField(this, "isReady", false);
			__publicField(this, "isPlaying", false);
			__publicField(this, "isLoading", true);
			__publicField(this, "loadOnReady", null);
			__publicField(this, "startOnPlay", true);
			__publicField(this, "seekOnPlay", null);
			__publicField(this, "onDurationCalled", false);
			__publicField(this, "handlePlayerMount", (player) => {
				if (this.player) {
					this.progress();
					return;
				}
				this.player = player;
				this.player.load(this.props.url);
				this.progress();
			});
			__publicField(this, "getInternalPlayer", (key) => {
				if (!this.player) return null;
				return this.player[key];
			});
			__publicField(this, "progress", () => {
				if (this.props.url && this.player && this.isReady) {
					const playedSeconds = this.getCurrentTime() || 0;
					const loadedSeconds = this.getSecondsLoaded();
					const duration = this.getDuration();
					if (duration) {
						const progress = {
							playedSeconds,
							played: playedSeconds / duration
						};
						if (loadedSeconds !== null) {
							progress.loadedSeconds = loadedSeconds;
							progress.loaded = loadedSeconds / duration;
						}
						if (progress.playedSeconds !== this.prevPlayed || progress.loadedSeconds !== this.prevLoaded) this.props.onProgress(progress);
						this.prevPlayed = progress.playedSeconds;
						this.prevLoaded = progress.loadedSeconds;
					}
				}
				this.progressTimeout = setTimeout(this.progress, this.props.progressFrequency || this.props.progressInterval);
			});
			__publicField(this, "handleReady", () => {
				if (!this.mounted) return;
				this.isReady = true;
				this.isLoading = false;
				const { onReady, playing, volume, muted } = this.props;
				onReady();
				if (!muted && volume !== null) this.player.setVolume(volume);
				if (this.loadOnReady) {
					this.player.load(this.loadOnReady, true);
					this.loadOnReady = null;
				} else if (playing) this.player.play();
				this.handleDurationCheck();
			});
			__publicField(this, "handlePlay", () => {
				this.isPlaying = true;
				this.isLoading = false;
				const { onStart, onPlay, playbackRate } = this.props;
				if (this.startOnPlay) {
					if (this.player.setPlaybackRate && playbackRate !== 1) this.player.setPlaybackRate(playbackRate);
					onStart();
					this.startOnPlay = false;
				}
				onPlay();
				if (this.seekOnPlay) {
					this.seekTo(this.seekOnPlay);
					this.seekOnPlay = null;
				}
				this.handleDurationCheck();
			});
			__publicField(this, "handlePause", (e) => {
				this.isPlaying = false;
				if (!this.isLoading) this.props.onPause(e);
			});
			__publicField(this, "handleEnded", () => {
				const { activePlayer, loop, onEnded } = this.props;
				if (activePlayer.loopOnEnded && loop) this.seekTo(0);
				if (!loop) {
					this.isPlaying = false;
					onEnded();
				}
			});
			__publicField(this, "handleError", (...args) => {
				this.isLoading = false;
				this.props.onError(...args);
			});
			__publicField(this, "handleDurationCheck", () => {
				clearTimeout(this.durationCheckTimeout);
				const duration = this.getDuration();
				if (duration) {
					if (!this.onDurationCalled) {
						this.props.onDuration(duration);
						this.onDurationCalled = true;
					}
				} else this.durationCheckTimeout = setTimeout(this.handleDurationCheck, 100);
			});
			__publicField(this, "handleLoaded", () => {
				this.isLoading = false;
			});
		}
		componentDidMount() {
			this.mounted = true;
		}
		componentWillUnmount() {
			clearTimeout(this.progressTimeout);
			clearTimeout(this.durationCheckTimeout);
			if (this.isReady && this.props.stopOnUnmount) {
				this.player.stop();
				if (this.player.disablePIP) this.player.disablePIP();
			}
			this.mounted = false;
		}
		componentDidUpdate(prevProps) {
			if (!this.player) return;
			const { url, playing, volume, muted, playbackRate, pip, loop, activePlayer, disableDeferredLoading } = this.props;
			if (!(0, import_react_fast_compare.default)(prevProps.url, url)) {
				if (this.isLoading && !activePlayer.forceLoad && !disableDeferredLoading && !(0, import_utils.isMediaStream)(url)) {
					console.warn(`ReactPlayer: the attempt to load ${url} is being deferred until the player has loaded`);
					this.loadOnReady = url;
					return;
				}
				this.isLoading = true;
				this.startOnPlay = true;
				this.onDurationCalled = false;
				this.player.load(url, this.isReady);
			}
			if (!prevProps.playing && playing && !this.isPlaying) this.player.play();
			if (prevProps.playing && !playing && this.isPlaying) this.player.pause();
			if (!prevProps.pip && pip && this.player.enablePIP) this.player.enablePIP();
			if (prevProps.pip && !pip && this.player.disablePIP) this.player.disablePIP();
			if (prevProps.volume !== volume && volume !== null) this.player.setVolume(volume);
			if (prevProps.muted !== muted) if (muted) this.player.mute();
			else {
				this.player.unmute();
				if (volume !== null) setTimeout(() => this.player.setVolume(volume));
			}
			if (prevProps.playbackRate !== playbackRate && this.player.setPlaybackRate) this.player.setPlaybackRate(playbackRate);
			if (prevProps.loop !== loop && this.player.setLoop) this.player.setLoop(loop);
		}
		getDuration() {
			if (!this.isReady) return null;
			return this.player.getDuration();
		}
		getCurrentTime() {
			if (!this.isReady) return null;
			return this.player.getCurrentTime();
		}
		getSecondsLoaded() {
			if (!this.isReady) return null;
			return this.player.getSecondsLoaded();
		}
		seekTo(amount, type, keepPlaying) {
			if (!this.isReady) {
				if (amount !== 0) {
					this.seekOnPlay = amount;
					setTimeout(() => {
						this.seekOnPlay = null;
					}, SEEK_ON_PLAY_EXPIRY);
				}
				return;
			}
			if (!type ? amount > 0 && amount < 1 : type === "fraction") {
				const duration = this.player.getDuration();
				if (!duration) {
					console.warn("ReactPlayer: could not seek using fraction –\xA0duration not yet available");
					return;
				}
				this.player.seekTo(duration * amount, keepPlaying);
				return;
			}
			this.player.seekTo(amount, keepPlaying);
		}
		render() {
			const Player2 = this.props.activePlayer;
			if (!Player2) return null;
			return /* @__PURE__ */ import_react.default.createElement(Player2, {
				...this.props,
				onMount: this.handlePlayerMount,
				onReady: this.handleReady,
				onPlay: this.handlePlay,
				onPause: this.handlePause,
				onEnded: this.handleEnded,
				onLoaded: this.handleLoaded,
				onError: this.handleError
			});
		}
	};
	__publicField(Player, "displayName", "Player");
	__publicField(Player, "propTypes", import_props.propTypes);
	__publicField(Player, "defaultProps", import_props.defaultProps);
}));
//#endregion
//#region node_modules/react-player/lib/ReactPlayer.js
var require_ReactPlayer = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var __create = Object.create;
	var __defProp = Object.defineProperty;
	var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
	var __getOwnPropNames = Object.getOwnPropertyNames;
	var __getProtoOf = Object.getPrototypeOf;
	var __hasOwnProp = Object.prototype.hasOwnProperty;
	var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, {
		enumerable: true,
		configurable: true,
		writable: true,
		value
	}) : obj[key] = value;
	var __export = (target, all) => {
		for (var name in all) __defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	};
	var __copyProps = (to, from, except, desc) => {
		if (from && typeof from === "object" || typeof from === "function") {
			for (let key of __getOwnPropNames(from)) if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
				get: () => from[key],
				enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
			});
		}
		return to;
	};
	var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", {
		value: mod,
		enumerable: true
	}) : target, mod));
	var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
	var __publicField = (obj, key, value) => {
		__defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
		return value;
	};
	var ReactPlayer_exports = {};
	__export(ReactPlayer_exports, { createReactPlayer: () => createReactPlayer });
	module.exports = __toCommonJS(ReactPlayer_exports);
	var import_react = __toESM(require_react());
	var import_deepmerge = __toESM(require_cjs());
	var import_memoize_one = __toESM((init_memoize_one_esm(), __toCommonJS(memoize_one_esm_exports)));
	var import_react_fast_compare = __toESM(require_react_fast_compare());
	var import_props = require_props();
	var import_utils = require_utils();
	var import_Player = __toESM(require_Player());
	var Preview = (0, import_utils.lazy)(() => import(
		/* webpackChunkName: 'reactPlayerPreview' */
		"./Preview-D3y3pAED.js"
).then((m) => /* @__PURE__ */ __toESM(m.default)));
	var IS_BROWSER = typeof window !== "undefined" && window.document && typeof document !== "undefined";
	var IS_GLOBAL = typeof global !== "undefined" && global.window && global.window.document;
	var SUPPORTED_PROPS = Object.keys(import_props.propTypes);
	var UniversalSuspense = IS_BROWSER || IS_GLOBAL ? import_react.Suspense : () => null;
	var customPlayers = [];
	var createReactPlayer = (players, fallback) => {
		var _a;
		return _a = class extends import_react.Component {
			constructor() {
				super(...arguments);
				__publicField(this, "state", { showPreview: !!this.props.light });
				__publicField(this, "references", {
					wrapper: (wrapper) => {
						this.wrapper = wrapper;
					},
					player: (player) => {
						this.player = player;
					}
				});
				__publicField(this, "handleClickPreview", (e) => {
					this.setState({ showPreview: false });
					this.props.onClickPreview(e);
				});
				__publicField(this, "showPreview", () => {
					this.setState({ showPreview: true });
				});
				__publicField(this, "getDuration", () => {
					if (!this.player) return null;
					return this.player.getDuration();
				});
				__publicField(this, "getCurrentTime", () => {
					if (!this.player) return null;
					return this.player.getCurrentTime();
				});
				__publicField(this, "getSecondsLoaded", () => {
					if (!this.player) return null;
					return this.player.getSecondsLoaded();
				});
				__publicField(this, "getInternalPlayer", (key = "player") => {
					if (!this.player) return null;
					return this.player.getInternalPlayer(key);
				});
				__publicField(this, "seekTo", (fraction, type, keepPlaying) => {
					if (!this.player) return null;
					this.player.seekTo(fraction, type, keepPlaying);
				});
				__publicField(this, "handleReady", () => {
					this.props.onReady(this);
				});
				__publicField(this, "getActivePlayer", (0, import_memoize_one.default)((url) => {
					for (const player of [...customPlayers, ...players]) if (player.canPlay(url)) return player;
					if (fallback) return fallback;
					return null;
				}));
				__publicField(this, "getConfig", (0, import_memoize_one.default)((url, key) => {
					const { config } = this.props;
					return import_deepmerge.default.all([
						import_props.defaultProps.config,
						import_props.defaultProps.config[key] || {},
						config,
						config[key] || {}
					]);
				}));
				__publicField(this, "getAttributes", (0, import_memoize_one.default)((url) => {
					return (0, import_utils.omit)(this.props, SUPPORTED_PROPS);
				}));
				__publicField(this, "renderActivePlayer", (url) => {
					if (!url) return null;
					const player = this.getActivePlayer(url);
					if (!player) return null;
					const config = this.getConfig(url, player.key);
					return /* @__PURE__ */ import_react.default.createElement(import_Player.default, {
						...this.props,
						key: player.key,
						ref: this.references.player,
						config,
						activePlayer: player.lazyPlayer || player,
						onReady: this.handleReady
					});
				});
			}
			shouldComponentUpdate(nextProps, nextState) {
				return !(0, import_react_fast_compare.default)(this.props, nextProps) || !(0, import_react_fast_compare.default)(this.state, nextState);
			}
			componentDidUpdate(prevProps) {
				const { light } = this.props;
				if (!prevProps.light && light) this.setState({ showPreview: true });
				if (prevProps.light && !light) this.setState({ showPreview: false });
			}
			renderPreview(url) {
				if (!url) return null;
				const { light, playIcon, previewTabIndex, oEmbedUrl, previewAriaLabel } = this.props;
				return /* @__PURE__ */ import_react.default.createElement(Preview, {
					url,
					light,
					playIcon,
					previewTabIndex,
					previewAriaLabel,
					oEmbedUrl,
					onClick: this.handleClickPreview
				});
			}
			render() {
				const { url, style, width, height, fallback: fallback2, wrapper: Wrapper } = this.props;
				const { showPreview } = this.state;
				const attributes = this.getAttributes(url);
				const wrapperRef = typeof Wrapper === "string" ? this.references.wrapper : void 0;
				return /* @__PURE__ */ import_react.default.createElement(Wrapper, {
					ref: wrapperRef,
					style: {
						...style,
						width,
						height
					},
					...attributes
				}, /* @__PURE__ */ import_react.default.createElement(UniversalSuspense, { fallback: fallback2 }, showPreview ? this.renderPreview(url) : this.renderActivePlayer(url)));
			}
		}, __publicField(_a, "displayName", "ReactPlayer"), __publicField(_a, "propTypes", import_props.propTypes), __publicField(_a, "defaultProps", import_props.defaultProps), __publicField(_a, "addCustomPlayer", (player) => {
			customPlayers.push(player);
		}), __publicField(_a, "removeCustomPlayers", () => {
			customPlayers.length = 0;
		}), __publicField(_a, "canPlay", (url) => {
			for (const Player2 of [...customPlayers, ...players]) if (Player2.canPlay(url)) return true;
			return false;
		}), __publicField(_a, "canEnablePIP", (url) => {
			for (const Player2 of [...customPlayers, ...players]) if (Player2.canEnablePIP && Player2.canEnablePIP(url)) return true;
			return false;
		}), _a;
	};
}));
//#endregion
//#region node_modules/react-player/lib/patterns.js
var require_patterns = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var __defProp = Object.defineProperty;
	var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
	var __getOwnPropNames = Object.getOwnPropertyNames;
	var __hasOwnProp = Object.prototype.hasOwnProperty;
	var __export = (target, all) => {
		for (var name in all) __defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	};
	var __copyProps = (to, from, except, desc) => {
		if (from && typeof from === "object" || typeof from === "function") {
			for (let key of __getOwnPropNames(from)) if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
				get: () => from[key],
				enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
			});
		}
		return to;
	};
	var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
	var patterns_exports = {};
	__export(patterns_exports, {
		AUDIO_EXTENSIONS: () => AUDIO_EXTENSIONS,
		DASH_EXTENSIONS: () => DASH_EXTENSIONS,
		FLV_EXTENSIONS: () => FLV_EXTENSIONS,
		HLS_EXTENSIONS: () => HLS_EXTENSIONS,
		MATCH_URL_DAILYMOTION: () => MATCH_URL_DAILYMOTION,
		MATCH_URL_FACEBOOK: () => MATCH_URL_FACEBOOK,
		MATCH_URL_FACEBOOK_WATCH: () => MATCH_URL_FACEBOOK_WATCH,
		MATCH_URL_KALTURA: () => MATCH_URL_KALTURA,
		MATCH_URL_MIXCLOUD: () => MATCH_URL_MIXCLOUD,
		MATCH_URL_MUX: () => MATCH_URL_MUX,
		MATCH_URL_SOUNDCLOUD: () => MATCH_URL_SOUNDCLOUD,
		MATCH_URL_STREAMABLE: () => MATCH_URL_STREAMABLE,
		MATCH_URL_TWITCH_CHANNEL: () => MATCH_URL_TWITCH_CHANNEL,
		MATCH_URL_TWITCH_VIDEO: () => MATCH_URL_TWITCH_VIDEO,
		MATCH_URL_VIDYARD: () => MATCH_URL_VIDYARD,
		MATCH_URL_VIMEO: () => MATCH_URL_VIMEO,
		MATCH_URL_WISTIA: () => MATCH_URL_WISTIA,
		MATCH_URL_YOUTUBE: () => MATCH_URL_YOUTUBE,
		VIDEO_EXTENSIONS: () => VIDEO_EXTENSIONS,
		canPlay: () => canPlay
	});
	module.exports = __toCommonJS(patterns_exports);
	var import_utils = require_utils();
	var MATCH_URL_YOUTUBE = /(?:youtu\.be\/|youtube(?:-nocookie|education)?\.com\/(?:embed\/|v\/|watch\/|watch\?v=|watch\?.+&v=|shorts\/|live\/))((\w|-){11})|youtube\.com\/playlist\?list=|youtube\.com\/user\//;
	var MATCH_URL_SOUNDCLOUD = /(?:soundcloud\.com|snd\.sc)\/[^.]+$/;
	var MATCH_URL_VIMEO = /vimeo\.com\/(?!progressive_redirect).+/;
	var MATCH_URL_MUX = /stream\.mux\.com\/(?!\w+\.m3u8)(\w+)/;
	var MATCH_URL_FACEBOOK = /^https?:\/\/(www\.)?facebook\.com.*\/(video(s)?|watch|story)(\.php?|\/).+$/;
	var MATCH_URL_FACEBOOK_WATCH = /^https?:\/\/fb\.watch\/.+$/;
	var MATCH_URL_STREAMABLE = /streamable\.com\/([a-z0-9]+)$/;
	var MATCH_URL_WISTIA = /(?:wistia\.(?:com|net)|wi\.st)\/(?:medias|embed)\/(?:iframe\/)?([^?]+)/;
	var MATCH_URL_TWITCH_VIDEO = /(?:www\.|go\.)?twitch\.tv\/videos\/(\d+)($|\?)/;
	var MATCH_URL_TWITCH_CHANNEL = /(?:www\.|go\.)?twitch\.tv\/([a-zA-Z0-9_]+)($|\?)/;
	var MATCH_URL_DAILYMOTION = /^(?:(?:https?):)?(?:\/\/)?(?:www\.)?(?:(?:dailymotion\.com(?:\/embed)?\/video)|dai\.ly)\/([a-zA-Z0-9]+)(?:_[\w_-]+)?(?:[\w.#_-]+)?/;
	var MATCH_URL_MIXCLOUD = /mixcloud\.com\/([^/]+\/[^/]+)/;
	var MATCH_URL_VIDYARD = /vidyard.com\/(?:watch\/)?([a-zA-Z0-9-_]+)/;
	var MATCH_URL_KALTURA = /^https?:\/\/[a-zA-Z]+\.kaltura.(com|org)\/p\/([0-9]+)\/sp\/([0-9]+)00\/embedIframeJs\/uiconf_id\/([0-9]+)\/partner_id\/([0-9]+)(.*)entry_id.([a-zA-Z0-9-_].*)$/;
	var AUDIO_EXTENSIONS = /\.(m4a|m4b|mp4a|mpga|mp2|mp2a|mp3|m2a|m3a|wav|weba|aac|oga|spx)($|\?)/i;
	var VIDEO_EXTENSIONS = /\.(mp4|og[gv]|webm|mov|m4v)(#t=[,\d+]+)?($|\?)/i;
	var HLS_EXTENSIONS = /\.(m3u8)($|\?)/i;
	var DASH_EXTENSIONS = /\.(mpd)($|\?)/i;
	var FLV_EXTENSIONS = /\.(flv)($|\?)/i;
	var canPlayFile = (url) => {
		if (url instanceof Array) {
			for (const item of url) {
				if (typeof item === "string" && canPlayFile(item)) return true;
				if (canPlayFile(item.src)) return true;
			}
			return false;
		}
		if ((0, import_utils.isMediaStream)(url) || (0, import_utils.isBlobUrl)(url)) return true;
		return AUDIO_EXTENSIONS.test(url) || VIDEO_EXTENSIONS.test(url) || HLS_EXTENSIONS.test(url) || DASH_EXTENSIONS.test(url) || FLV_EXTENSIONS.test(url);
	};
	var canPlay = {
		youtube: (url) => {
			if (url instanceof Array) return url.every((item) => MATCH_URL_YOUTUBE.test(item));
			return MATCH_URL_YOUTUBE.test(url);
		},
		soundcloud: (url) => MATCH_URL_SOUNDCLOUD.test(url) && !AUDIO_EXTENSIONS.test(url),
		vimeo: (url) => MATCH_URL_VIMEO.test(url) && !VIDEO_EXTENSIONS.test(url) && !HLS_EXTENSIONS.test(url),
		mux: (url) => MATCH_URL_MUX.test(url),
		facebook: (url) => MATCH_URL_FACEBOOK.test(url) || MATCH_URL_FACEBOOK_WATCH.test(url),
		streamable: (url) => MATCH_URL_STREAMABLE.test(url),
		wistia: (url) => MATCH_URL_WISTIA.test(url),
		twitch: (url) => MATCH_URL_TWITCH_VIDEO.test(url) || MATCH_URL_TWITCH_CHANNEL.test(url),
		dailymotion: (url) => MATCH_URL_DAILYMOTION.test(url),
		mixcloud: (url) => MATCH_URL_MIXCLOUD.test(url),
		vidyard: (url) => MATCH_URL_VIDYARD.test(url),
		kaltura: (url) => MATCH_URL_KALTURA.test(url),
		file: canPlayFile
	};
}));
//#endregion
//#region node_modules/react-player/lib/players/YouTube.js
var require_YouTube = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var __create = Object.create;
	var __defProp = Object.defineProperty;
	var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
	var __getOwnPropNames = Object.getOwnPropertyNames;
	var __getProtoOf = Object.getPrototypeOf;
	var __hasOwnProp = Object.prototype.hasOwnProperty;
	var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, {
		enumerable: true,
		configurable: true,
		writable: true,
		value
	}) : obj[key] = value;
	var __export = (target, all) => {
		for (var name in all) __defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	};
	var __copyProps = (to, from, except, desc) => {
		if (from && typeof from === "object" || typeof from === "function") {
			for (let key of __getOwnPropNames(from)) if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
				get: () => from[key],
				enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
			});
		}
		return to;
	};
	var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", {
		value: mod,
		enumerable: true
	}) : target, mod));
	var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
	var __publicField = (obj, key, value) => {
		__defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
		return value;
	};
	var YouTube_exports = {};
	__export(YouTube_exports, { default: () => YouTube });
	module.exports = __toCommonJS(YouTube_exports);
	var import_react = __toESM(require_react());
	var import_utils = require_utils();
	var import_patterns = require_patterns();
	var SDK_URL = "https://www.youtube.com/iframe_api";
	var SDK_GLOBAL = "YT";
	var SDK_GLOBAL_READY = "onYouTubeIframeAPIReady";
	var MATCH_PLAYLIST = /[?&](?:list|channel)=([a-zA-Z0-9_-]+)/;
	var MATCH_USER_UPLOADS = /user\/([a-zA-Z0-9_-]+)\/?/;
	var MATCH_NOCOOKIE = /youtube-nocookie\.com/;
	var NOCOOKIE_HOST = "https://www.youtube-nocookie.com";
	var YouTube = class extends import_react.Component {
		constructor() {
			super(...arguments);
			__publicField(this, "callPlayer", import_utils.callPlayer);
			__publicField(this, "parsePlaylist", (url) => {
				if (url instanceof Array) return {
					listType: "playlist",
					playlist: url.map(this.getID).join(",")
				};
				if (MATCH_PLAYLIST.test(url)) {
					const [, playlistId] = url.match(MATCH_PLAYLIST);
					return {
						listType: "playlist",
						list: playlistId.replace(/^UC/, "UU")
					};
				}
				if (MATCH_USER_UPLOADS.test(url)) {
					const [, username] = url.match(MATCH_USER_UPLOADS);
					return {
						listType: "user_uploads",
						list: username
					};
				}
				return {};
			});
			__publicField(this, "onStateChange", (event) => {
				const { data } = event;
				const { onPlay, onPause, onBuffer, onBufferEnd, onEnded, onReady, loop, config: { playerVars, onUnstarted } } = this.props;
				const { UNSTARTED, PLAYING, PAUSED, BUFFERING, ENDED, CUED } = window[SDK_GLOBAL].PlayerState;
				if (data === UNSTARTED) onUnstarted();
				if (data === PLAYING) {
					onPlay();
					onBufferEnd();
				}
				if (data === PAUSED) onPause();
				if (data === BUFFERING) onBuffer();
				if (data === ENDED) {
					const isPlaylist = !!this.callPlayer("getPlaylist");
					if (loop && !isPlaylist) if (playerVars.start) this.seekTo(playerVars.start);
					else this.play();
					onEnded();
				}
				if (data === CUED) onReady();
			});
			__publicField(this, "mute", () => {
				this.callPlayer("mute");
			});
			__publicField(this, "unmute", () => {
				this.callPlayer("unMute");
			});
			__publicField(this, "ref", (container) => {
				this.container = container;
			});
		}
		componentDidMount() {
			this.props.onMount && this.props.onMount(this);
		}
		getID(url) {
			if (!url || url instanceof Array || MATCH_PLAYLIST.test(url)) return null;
			return url.match(import_patterns.MATCH_URL_YOUTUBE)[1];
		}
		load(url, isReady) {
			const { playing, muted, playsinline, controls, loop, config, onError } = this.props;
			const { playerVars, embedOptions } = config;
			const id = this.getID(url);
			if (isReady) {
				if (MATCH_PLAYLIST.test(url) || MATCH_USER_UPLOADS.test(url) || url instanceof Array) {
					this.player.loadPlaylist(this.parsePlaylist(url));
					return;
				}
				this.player.cueVideoById({
					videoId: id,
					startSeconds: (0, import_utils.parseStartTime)(url) || playerVars.start,
					endSeconds: (0, import_utils.parseEndTime)(url) || playerVars.end
				});
				return;
			}
			(0, import_utils.getSDK)(SDK_URL, SDK_GLOBAL, SDK_GLOBAL_READY, (YT) => YT.loaded).then((YT) => {
				if (!this.container) return;
				this.player = new YT.Player(this.container, {
					width: "100%",
					height: "100%",
					videoId: id,
					playerVars: {
						autoplay: playing ? 1 : 0,
						mute: muted ? 1 : 0,
						controls: controls ? 1 : 0,
						start: (0, import_utils.parseStartTime)(url),
						end: (0, import_utils.parseEndTime)(url),
						origin: window.location.origin,
						playsinline: playsinline ? 1 : 0,
						...this.parsePlaylist(url),
						...playerVars
					},
					events: {
						onReady: () => {
							if (loop) this.player.setLoop(true);
							this.props.onReady();
						},
						onPlaybackRateChange: (event) => this.props.onPlaybackRateChange(event.data),
						onPlaybackQualityChange: (event) => this.props.onPlaybackQualityChange(event),
						onStateChange: this.onStateChange,
						onError: (event) => onError(event.data)
					},
					host: MATCH_NOCOOKIE.test(url) ? NOCOOKIE_HOST : void 0,
					...embedOptions
				});
			}, onError);
			if (embedOptions.events) console.warn("Using `embedOptions.events` will likely break things. Use ReactPlayer’s callback props instead, eg onReady, onPlay, onPause");
		}
		play() {
			this.callPlayer("playVideo");
		}
		pause() {
			this.callPlayer("pauseVideo");
		}
		stop() {
			if (!document.body.contains(this.callPlayer("getIframe"))) return;
			this.callPlayer("stopVideo");
		}
		seekTo(amount, keepPlaying = false) {
			this.callPlayer("seekTo", amount);
			if (!keepPlaying && !this.props.playing) this.pause();
		}
		setVolume(fraction) {
			this.callPlayer("setVolume", fraction * 100);
		}
		setPlaybackRate(rate) {
			this.callPlayer("setPlaybackRate", rate);
		}
		setLoop(loop) {
			this.callPlayer("setLoop", loop);
		}
		getDuration() {
			return this.callPlayer("getDuration");
		}
		getCurrentTime() {
			return this.callPlayer("getCurrentTime");
		}
		getSecondsLoaded() {
			return this.callPlayer("getVideoLoadedFraction") * this.getDuration();
		}
		render() {
			const { display } = this.props;
			const style = {
				width: "100%",
				height: "100%",
				display
			};
			return /* @__PURE__ */ import_react.default.createElement("div", { style }, /* @__PURE__ */ import_react.default.createElement("div", { ref: this.ref }));
		}
	};
	__publicField(YouTube, "displayName", "YouTube");
	__publicField(YouTube, "canPlay", import_patterns.canPlay.youtube);
}));
//#endregion
//#region node_modules/react-player/youtube.js
var require_youtube = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	var createReactPlayer = require_ReactPlayer().createReactPlayer;
	var Player = require_YouTube().default;
	module.exports = createReactPlayer([{
		key: "youtube",
		canPlay: Player.canPlay,
		lazyPlayer: Player
	}]);
}));
//#endregion
export default require_youtube();

//# sourceMappingURL=react-player_youtube.js.map