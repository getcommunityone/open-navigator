import { a as __toESM } from "./chunk-_TIqcEvS.js";
import { t as require_react } from "./react.js";
import { t as require_react_dom } from "./react-dom-Dr7h9AAs.js";
//#region node_modules/@tanstack/virtual-core/dist/esm/utils.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_react_dom = /* @__PURE__ */ __toESM(require_react_dom());
function memo(getDeps, fn, opts) {
	let deps = opts.initialDeps ?? [];
	let result;
	let isInitial = true;
	function memoizedFunction() {
		var _a, _b, _c;
		let depTime;
		if (opts.key && ((_a = opts.debug) == null ? void 0 : _a.call(opts))) depTime = Date.now();
		const newDeps = getDeps();
		if (!(newDeps.length !== deps.length || newDeps.some((dep, index) => deps[index] !== dep))) return result;
		deps = newDeps;
		let resultTime;
		if (opts.key && ((_b = opts.debug) == null ? void 0 : _b.call(opts))) resultTime = Date.now();
		result = fn(...newDeps);
		if (opts.key && ((_c = opts.debug) == null ? void 0 : _c.call(opts))) {
			const depEndTime = Math.round((Date.now() - depTime) * 100) / 100;
			const resultEndTime = Math.round((Date.now() - resultTime) * 100) / 100;
			const resultFpsPercentage = resultEndTime / 16;
			const pad = (str, num) => {
				str = String(str);
				while (str.length < num) str = " " + str;
				return str;
			};
			console.info(`%c⏱ ${pad(resultEndTime, 5)} /${pad(depEndTime, 5)} ms`, `
            font-size: .6rem;
            font-weight: bold;
            color: hsl(${Math.max(0, Math.min(120 - 120 * resultFpsPercentage, 120))}deg 100% 31%);`, opts == null ? void 0 : opts.key);
		}
		if ((opts == null ? void 0 : opts.onChange) && !(isInitial && opts.skipInitialOnChange)) opts.onChange(result);
		isInitial = false;
		return result;
	}
	memoizedFunction.updateDeps = (newDeps) => {
		deps = newDeps;
	};
	return memoizedFunction;
}
function notUndefined(value, msg) {
	if (value === void 0) throw new Error(`Unexpected undefined${msg ? `: ${msg}` : ""}`);
	else return value;
}
var approxEqual = (a, b) => Math.abs(a - b) < 1.01;
var debounce = (targetWindow, fn, ms) => {
	let timeoutId;
	return function(...args) {
		targetWindow.clearTimeout(timeoutId);
		timeoutId = targetWindow.setTimeout(() => fn.apply(this, args), ms);
	};
};
//#endregion
//#region node_modules/@tanstack/virtual-core/dist/esm/index.js
var getRect = (element) => {
	const { offsetWidth, offsetHeight } = element;
	return {
		width: offsetWidth,
		height: offsetHeight
	};
};
var defaultKeyExtractor = (index) => index;
var defaultRangeExtractor = (range) => {
	const start = Math.max(range.startIndex - range.overscan, 0);
	const end = Math.min(range.endIndex + range.overscan, range.count - 1);
	const arr = [];
	for (let i = start; i <= end; i++) arr.push(i);
	return arr;
};
var observeElementRect = (instance, cb) => {
	const element = instance.scrollElement;
	if (!element) return;
	const targetWindow = instance.targetWindow;
	if (!targetWindow) return;
	const handler = (rect) => {
		const { width, height } = rect;
		cb({
			width: Math.round(width),
			height: Math.round(height)
		});
	};
	handler(getRect(element));
	if (!targetWindow.ResizeObserver) return () => {};
	const observer = new targetWindow.ResizeObserver((entries) => {
		const run = () => {
			const entry = entries[0];
			if (entry == null ? void 0 : entry.borderBoxSize) {
				const box = entry.borderBoxSize[0];
				if (box) {
					handler({
						width: box.inlineSize,
						height: box.blockSize
					});
					return;
				}
			}
			handler(getRect(element));
		};
		instance.options.useAnimationFrameWithResizeObserver ? requestAnimationFrame(run) : run();
	});
	observer.observe(element, { box: "border-box" });
	return () => {
		observer.unobserve(element);
	};
};
var addEventListenerOptions = { passive: true };
var supportsScrollend = typeof window == "undefined" ? true : "onscrollend" in window;
var observeElementOffset = (instance, cb) => {
	const element = instance.scrollElement;
	if (!element) return;
	const targetWindow = instance.targetWindow;
	if (!targetWindow) return;
	let offset = 0;
	const fallback = instance.options.useScrollendEvent && supportsScrollend ? () => void 0 : debounce(targetWindow, () => {
		cb(offset, false);
	}, instance.options.isScrollingResetDelay);
	const createHandler = (isScrolling) => () => {
		const { horizontal, isRtl } = instance.options;
		offset = horizontal ? element["scrollLeft"] * (isRtl && -1 || 1) : element["scrollTop"];
		fallback();
		cb(offset, isScrolling);
	};
	const handler = createHandler(true);
	const endHandler = createHandler(false);
	element.addEventListener("scroll", handler, addEventListenerOptions);
	const registerScrollendEvent = instance.options.useScrollendEvent && supportsScrollend;
	if (registerScrollendEvent) element.addEventListener("scrollend", endHandler, addEventListenerOptions);
	return () => {
		element.removeEventListener("scroll", handler);
		if (registerScrollendEvent) element.removeEventListener("scrollend", endHandler);
	};
};
var measureElement = (element, entry, instance) => {
	if (entry == null ? void 0 : entry.borderBoxSize) {
		const box = entry.borderBoxSize[0];
		if (box) return Math.round(box[instance.options.horizontal ? "inlineSize" : "blockSize"]);
	}
	return element[instance.options.horizontal ? "offsetWidth" : "offsetHeight"];
};
var elementScroll = (offset, { adjustments = 0, behavior }, instance) => {
	var _a, _b;
	const toOffset = offset + adjustments;
	(_b = (_a = instance.scrollElement) == null ? void 0 : _a.scrollTo) == null || _b.call(_a, {
		[instance.options.horizontal ? "left" : "top"]: toOffset,
		behavior
	});
};
var Virtualizer = class {
	constructor(opts) {
		this.unsubs = [];
		this.scrollElement = null;
		this.targetWindow = null;
		this.isScrolling = false;
		this.scrollState = null;
		this.measurementsCache = [];
		this.itemSizeCache = /* @__PURE__ */ new Map();
		this.laneAssignments = /* @__PURE__ */ new Map();
		this.pendingMeasuredCacheIndexes = [];
		this.prevLanes = void 0;
		this.lanesChangedFlag = false;
		this.lanesSettling = false;
		this.scrollRect = null;
		this.scrollOffset = null;
		this.scrollDirection = null;
		this.scrollAdjustments = 0;
		this.elementsCache = /* @__PURE__ */ new Map();
		this.now = () => {
			var _a, _b, _c;
			return ((_c = (_b = (_a = this.targetWindow) == null ? void 0 : _a.performance) == null ? void 0 : _b.now) == null ? void 0 : _c.call(_b)) ?? Date.now();
		};
		this.observer = /* @__PURE__ */ (() => {
			let _ro = null;
			const get = () => {
				if (_ro) return _ro;
				if (!this.targetWindow || !this.targetWindow.ResizeObserver) return null;
				return _ro = new this.targetWindow.ResizeObserver((entries) => {
					entries.forEach((entry) => {
						const run = () => {
							const node = entry.target;
							const index = this.indexFromElement(node);
							if (!node.isConnected) {
								this.observer.unobserve(node);
								return;
							}
							if (this.shouldMeasureDuringScroll(index)) this.resizeItem(index, this.options.measureElement(node, entry, this));
						};
						this.options.useAnimationFrameWithResizeObserver ? requestAnimationFrame(run) : run();
					});
				});
			};
			return {
				disconnect: () => {
					var _a;
					(_a = get()) == null || _a.disconnect();
					_ro = null;
				},
				observe: (target) => {
					var _a;
					return (_a = get()) == null ? void 0 : _a.observe(target, { box: "border-box" });
				},
				unobserve: (target) => {
					var _a;
					return (_a = get()) == null ? void 0 : _a.unobserve(target);
				}
			};
		})();
		this.range = null;
		this.setOptions = (opts2) => {
			Object.entries(opts2).forEach(([key, value]) => {
				if (typeof value === "undefined") delete opts2[key];
			});
			this.options = {
				debug: false,
				initialOffset: 0,
				overscan: 1,
				paddingStart: 0,
				paddingEnd: 0,
				scrollPaddingStart: 0,
				scrollPaddingEnd: 0,
				horizontal: false,
				getItemKey: defaultKeyExtractor,
				rangeExtractor: defaultRangeExtractor,
				onChange: () => {},
				measureElement,
				initialRect: {
					width: 0,
					height: 0
				},
				scrollMargin: 0,
				gap: 0,
				indexAttribute: "data-index",
				initialMeasurementsCache: [],
				lanes: 1,
				isScrollingResetDelay: 150,
				enabled: true,
				isRtl: false,
				useScrollendEvent: false,
				useAnimationFrameWithResizeObserver: false,
				laneAssignmentMode: "estimate",
				...opts2
			};
		};
		this.notify = (sync) => {
			var _a, _b;
			(_b = (_a = this.options).onChange) == null || _b.call(_a, this, sync);
		};
		this.maybeNotify = memo(() => {
			this.calculateRange();
			return [
				this.isScrolling,
				this.range ? this.range.startIndex : null,
				this.range ? this.range.endIndex : null
			];
		}, (isScrolling) => {
			this.notify(isScrolling);
		}, {
			key: "maybeNotify",
			debug: () => this.options.debug,
			initialDeps: [
				this.isScrolling,
				this.range ? this.range.startIndex : null,
				this.range ? this.range.endIndex : null
			]
		});
		this.cleanup = () => {
			this.unsubs.filter(Boolean).forEach((d) => d());
			this.unsubs = [];
			this.observer.disconnect();
			if (this.rafId != null && this.targetWindow) {
				this.targetWindow.cancelAnimationFrame(this.rafId);
				this.rafId = null;
			}
			this.scrollState = null;
			this.scrollElement = null;
			this.targetWindow = null;
		};
		this._didMount = () => {
			return () => {
				this.cleanup();
			};
		};
		this._willUpdate = () => {
			var _a;
			const scrollElement = this.options.enabled ? this.options.getScrollElement() : null;
			if (this.scrollElement !== scrollElement) {
				this.cleanup();
				if (!scrollElement) {
					this.maybeNotify();
					return;
				}
				this.scrollElement = scrollElement;
				if (this.scrollElement && "ownerDocument" in this.scrollElement) this.targetWindow = this.scrollElement.ownerDocument.defaultView;
				else this.targetWindow = ((_a = this.scrollElement) == null ? void 0 : _a.window) ?? null;
				this.elementsCache.forEach((cached) => {
					this.observer.observe(cached);
				});
				this.unsubs.push(this.options.observeElementRect(this, (rect) => {
					this.scrollRect = rect;
					this.maybeNotify();
				}));
				this.unsubs.push(this.options.observeElementOffset(this, (offset, isScrolling) => {
					this.scrollAdjustments = 0;
					this.scrollDirection = isScrolling ? this.getScrollOffset() < offset ? "forward" : "backward" : null;
					this.scrollOffset = offset;
					this.isScrolling = isScrolling;
					if (this.scrollState) this.scheduleScrollReconcile();
					this.maybeNotify();
				}));
				this._scrollToOffset(this.getScrollOffset(), {
					adjustments: void 0,
					behavior: void 0
				});
			}
		};
		this.rafId = null;
		this.getSize = () => {
			if (!this.options.enabled) {
				this.scrollRect = null;
				return 0;
			}
			this.scrollRect = this.scrollRect ?? this.options.initialRect;
			return this.scrollRect[this.options.horizontal ? "width" : "height"];
		};
		this.getScrollOffset = () => {
			if (!this.options.enabled) {
				this.scrollOffset = null;
				return 0;
			}
			this.scrollOffset = this.scrollOffset ?? (typeof this.options.initialOffset === "function" ? this.options.initialOffset() : this.options.initialOffset);
			return this.scrollOffset;
		};
		this.getFurthestMeasurement = (measurements, index) => {
			const furthestMeasurementsFound = /* @__PURE__ */ new Map();
			const furthestMeasurements = /* @__PURE__ */ new Map();
			for (let m = index - 1; m >= 0; m--) {
				const measurement = measurements[m];
				if (furthestMeasurementsFound.has(measurement.lane)) continue;
				const previousFurthestMeasurement = furthestMeasurements.get(measurement.lane);
				if (previousFurthestMeasurement == null || measurement.end > previousFurthestMeasurement.end) furthestMeasurements.set(measurement.lane, measurement);
				else if (measurement.end < previousFurthestMeasurement.end) furthestMeasurementsFound.set(measurement.lane, true);
				if (furthestMeasurementsFound.size === this.options.lanes) break;
			}
			return furthestMeasurements.size === this.options.lanes ? Array.from(furthestMeasurements.values()).sort((a, b) => {
				if (a.end === b.end) return a.index - b.index;
				return a.end - b.end;
			})[0] : void 0;
		};
		this.getMeasurementOptions = memo(() => [
			this.options.count,
			this.options.paddingStart,
			this.options.scrollMargin,
			this.options.getItemKey,
			this.options.enabled,
			this.options.lanes,
			this.options.laneAssignmentMode
		], (count, paddingStart, scrollMargin, getItemKey, enabled, lanes, laneAssignmentMode) => {
			if (this.prevLanes !== void 0 && this.prevLanes !== lanes) this.lanesChangedFlag = true;
			this.prevLanes = lanes;
			this.pendingMeasuredCacheIndexes = [];
			return {
				count,
				paddingStart,
				scrollMargin,
				getItemKey,
				enabled,
				lanes,
				laneAssignmentMode
			};
		}, { key: false });
		this.getMeasurements = memo(() => [this.getMeasurementOptions(), this.itemSizeCache], ({ count, paddingStart, scrollMargin, getItemKey, enabled, lanes, laneAssignmentMode }, itemSizeCache) => {
			if (!enabled) {
				this.measurementsCache = [];
				this.itemSizeCache.clear();
				this.laneAssignments.clear();
				return [];
			}
			if (this.laneAssignments.size > count) {
				for (const index of this.laneAssignments.keys()) if (index >= count) this.laneAssignments.delete(index);
			}
			if (this.lanesChangedFlag) {
				this.lanesChangedFlag = false;
				this.lanesSettling = true;
				this.measurementsCache = [];
				this.itemSizeCache.clear();
				this.laneAssignments.clear();
				this.pendingMeasuredCacheIndexes = [];
			}
			if (this.measurementsCache.length === 0 && !this.lanesSettling) {
				this.measurementsCache = this.options.initialMeasurementsCache;
				this.measurementsCache.forEach((item) => {
					this.itemSizeCache.set(item.key, item.size);
				});
			}
			const min = this.lanesSettling ? 0 : this.pendingMeasuredCacheIndexes.length > 0 ? Math.min(...this.pendingMeasuredCacheIndexes) : 0;
			this.pendingMeasuredCacheIndexes = [];
			if (this.lanesSettling && this.measurementsCache.length === count) this.lanesSettling = false;
			const measurements = this.measurementsCache.slice(0, min);
			const laneLastIndex = new Array(lanes).fill(void 0);
			for (let m = 0; m < min; m++) {
				const item = measurements[m];
				if (item) laneLastIndex[item.lane] = m;
			}
			for (let i = min; i < count; i++) {
				const key = getItemKey(i);
				const cachedLane = this.laneAssignments.get(i);
				let lane;
				let start;
				const shouldCacheLane = laneAssignmentMode === "estimate" || itemSizeCache.has(key);
				if (cachedLane !== void 0 && this.options.lanes > 1) {
					lane = cachedLane;
					const prevIndex = laneLastIndex[lane];
					const prevInLane = prevIndex !== void 0 ? measurements[prevIndex] : void 0;
					start = prevInLane ? prevInLane.end + this.options.gap : paddingStart + scrollMargin;
				} else {
					const furthestMeasurement = this.options.lanes === 1 ? measurements[i - 1] : this.getFurthestMeasurement(measurements, i);
					start = furthestMeasurement ? furthestMeasurement.end + this.options.gap : paddingStart + scrollMargin;
					lane = furthestMeasurement ? furthestMeasurement.lane : i % this.options.lanes;
					if (this.options.lanes > 1 && shouldCacheLane) this.laneAssignments.set(i, lane);
				}
				const measuredSize = itemSizeCache.get(key);
				const size = typeof measuredSize === "number" ? measuredSize : this.options.estimateSize(i);
				const end = start + size;
				measurements[i] = {
					index: i,
					start,
					size,
					end,
					key,
					lane
				};
				laneLastIndex[lane] = i;
			}
			this.measurementsCache = measurements;
			return measurements;
		}, {
			key: "getMeasurements",
			debug: () => this.options.debug
		});
		this.calculateRange = memo(() => [
			this.getMeasurements(),
			this.getSize(),
			this.getScrollOffset(),
			this.options.lanes
		], (measurements, outerSize, scrollOffset, lanes) => {
			return this.range = measurements.length > 0 && outerSize > 0 ? calculateRange({
				measurements,
				outerSize,
				scrollOffset,
				lanes
			}) : null;
		}, {
			key: "calculateRange",
			debug: () => this.options.debug
		});
		this.getVirtualIndexes = memo(() => {
			let startIndex = null;
			let endIndex = null;
			const range = this.calculateRange();
			if (range) {
				startIndex = range.startIndex;
				endIndex = range.endIndex;
			}
			this.maybeNotify.updateDeps([
				this.isScrolling,
				startIndex,
				endIndex
			]);
			return [
				this.options.rangeExtractor,
				this.options.overscan,
				this.options.count,
				startIndex,
				endIndex
			];
		}, (rangeExtractor, overscan, count, startIndex, endIndex) => {
			return startIndex === null || endIndex === null ? [] : rangeExtractor({
				startIndex,
				endIndex,
				overscan,
				count
			});
		}, {
			key: "getVirtualIndexes",
			debug: () => this.options.debug
		});
		this.indexFromElement = (node) => {
			const attributeName = this.options.indexAttribute;
			const indexStr = node.getAttribute(attributeName);
			if (!indexStr) {
				console.warn(`Missing attribute name '${attributeName}={index}' on measured element.`);
				return -1;
			}
			return parseInt(indexStr, 10);
		};
		this.shouldMeasureDuringScroll = (index) => {
			var _a;
			if (!this.scrollState || this.scrollState.behavior !== "smooth") return true;
			const scrollIndex = this.scrollState.index ?? ((_a = this.getVirtualItemForOffset(this.scrollState.lastTargetOffset)) == null ? void 0 : _a.index);
			if (scrollIndex !== void 0 && this.range) {
				const bufferSize = Math.max(this.options.overscan, Math.ceil((this.range.endIndex - this.range.startIndex) / 2));
				const minIndex = Math.max(0, scrollIndex - bufferSize);
				const maxIndex = Math.min(this.options.count - 1, scrollIndex + bufferSize);
				return index >= minIndex && index <= maxIndex;
			}
			return true;
		};
		this.measureElement = (node) => {
			if (!node) {
				this.elementsCache.forEach((cached, key2) => {
					if (!cached.isConnected) {
						this.observer.unobserve(cached);
						this.elementsCache.delete(key2);
					}
				});
				return;
			}
			const index = this.indexFromElement(node);
			const key = this.options.getItemKey(index);
			const prevNode = this.elementsCache.get(key);
			if (prevNode !== node) {
				if (prevNode) this.observer.unobserve(prevNode);
				this.observer.observe(node);
				this.elementsCache.set(key, node);
			}
			if ((!this.isScrolling || this.scrollState) && this.shouldMeasureDuringScroll(index)) this.resizeItem(index, this.options.measureElement(node, void 0, this));
		};
		this.resizeItem = (index, size) => {
			var _a;
			const item = this.measurementsCache[index];
			if (!item) return;
			const delta = size - (this.itemSizeCache.get(item.key) ?? item.size);
			if (delta !== 0) {
				if (((_a = this.scrollState) == null ? void 0 : _a.behavior) !== "smooth" && (this.shouldAdjustScrollPositionOnItemSizeChange !== void 0 ? this.shouldAdjustScrollPositionOnItemSizeChange(item, delta, this) : item.start < this.getScrollOffset() + this.scrollAdjustments)) {
					if (this.options.debug) console.info("correction", delta);
					this._scrollToOffset(this.getScrollOffset(), {
						adjustments: this.scrollAdjustments += delta,
						behavior: void 0
					});
				}
				this.pendingMeasuredCacheIndexes.push(item.index);
				this.itemSizeCache = new Map(this.itemSizeCache.set(item.key, size));
				this.notify(false);
			}
		};
		this.getVirtualItems = memo(() => [this.getVirtualIndexes(), this.getMeasurements()], (indexes, measurements) => {
			const virtualItems = [];
			for (let k = 0, len = indexes.length; k < len; k++) {
				const measurement = measurements[indexes[k]];
				virtualItems.push(measurement);
			}
			return virtualItems;
		}, {
			key: "getVirtualItems",
			debug: () => this.options.debug
		});
		this.getVirtualItemForOffset = (offset) => {
			const measurements = this.getMeasurements();
			if (measurements.length === 0) return;
			return notUndefined(measurements[findNearestBinarySearch(0, measurements.length - 1, (index) => notUndefined(measurements[index]).start, offset)]);
		};
		this.getMaxScrollOffset = () => {
			if (!this.scrollElement) return 0;
			if ("scrollHeight" in this.scrollElement) return this.options.horizontal ? this.scrollElement.scrollWidth - this.scrollElement.clientWidth : this.scrollElement.scrollHeight - this.scrollElement.clientHeight;
			else {
				const doc = this.scrollElement.document.documentElement;
				return this.options.horizontal ? doc.scrollWidth - this.scrollElement.innerWidth : doc.scrollHeight - this.scrollElement.innerHeight;
			}
		};
		this.getOffsetForAlignment = (toOffset, align, itemSize = 0) => {
			if (!this.scrollElement) return 0;
			const size = this.getSize();
			const scrollOffset = this.getScrollOffset();
			if (align === "auto") align = toOffset >= scrollOffset + size ? "end" : "start";
			if (align === "center") toOffset += (itemSize - size) / 2;
			else if (align === "end") toOffset -= size;
			const maxOffset = this.getMaxScrollOffset();
			return Math.max(Math.min(maxOffset, toOffset), 0);
		};
		this.getOffsetForIndex = (index, align = "auto") => {
			index = Math.max(0, Math.min(index, this.options.count - 1));
			const size = this.getSize();
			const scrollOffset = this.getScrollOffset();
			const item = this.measurementsCache[index];
			if (!item) return;
			if (align === "auto") if (item.end >= scrollOffset + size - this.options.scrollPaddingEnd) align = "end";
			else if (item.start <= scrollOffset + this.options.scrollPaddingStart) align = "start";
			else return [scrollOffset, align];
			if (align === "end" && index === this.options.count - 1) return [this.getMaxScrollOffset(), align];
			const toOffset = align === "end" ? item.end + this.options.scrollPaddingEnd : item.start - this.options.scrollPaddingStart;
			return [this.getOffsetForAlignment(toOffset, align, item.size), align];
		};
		this.scrollToOffset = (toOffset, { align = "start", behavior = "auto" } = {}) => {
			const offset = this.getOffsetForAlignment(toOffset, align);
			const now = this.now();
			this.scrollState = {
				index: null,
				align,
				behavior,
				startedAt: now,
				lastTargetOffset: offset,
				stableFrames: 0
			};
			this._scrollToOffset(offset, {
				adjustments: void 0,
				behavior
			});
			this.scheduleScrollReconcile();
		};
		this.scrollToIndex = (index, { align: initialAlign = "auto", behavior = "auto" } = {}) => {
			index = Math.max(0, Math.min(index, this.options.count - 1));
			const offsetInfo = this.getOffsetForIndex(index, initialAlign);
			if (!offsetInfo) return;
			const [offset, align] = offsetInfo;
			const now = this.now();
			this.scrollState = {
				index,
				align,
				behavior,
				startedAt: now,
				lastTargetOffset: offset,
				stableFrames: 0
			};
			this._scrollToOffset(offset, {
				adjustments: void 0,
				behavior
			});
			this.scheduleScrollReconcile();
		};
		this.scrollBy = (delta, { behavior = "auto" } = {}) => {
			const offset = this.getScrollOffset() + delta;
			const now = this.now();
			this.scrollState = {
				index: null,
				align: "start",
				behavior,
				startedAt: now,
				lastTargetOffset: offset,
				stableFrames: 0
			};
			this._scrollToOffset(offset, {
				adjustments: void 0,
				behavior
			});
			this.scheduleScrollReconcile();
		};
		this.getTotalSize = () => {
			var _a;
			const measurements = this.getMeasurements();
			let end;
			if (measurements.length === 0) end = this.options.paddingStart;
			else if (this.options.lanes === 1) end = ((_a = measurements[measurements.length - 1]) == null ? void 0 : _a.end) ?? 0;
			else {
				const endByLane = Array(this.options.lanes).fill(null);
				let endIndex = measurements.length - 1;
				while (endIndex >= 0 && endByLane.some((val) => val === null)) {
					const item = measurements[endIndex];
					if (endByLane[item.lane] === null) endByLane[item.lane] = item.end;
					endIndex--;
				}
				end = Math.max(...endByLane.filter((val) => val !== null));
			}
			return Math.max(end - this.options.scrollMargin + this.options.paddingEnd, 0);
		};
		this._scrollToOffset = (offset, { adjustments, behavior }) => {
			this.options.scrollToFn(offset, {
				behavior,
				adjustments
			}, this);
		};
		this.measure = () => {
			this.itemSizeCache = /* @__PURE__ */ new Map();
			this.laneAssignments = /* @__PURE__ */ new Map();
			this.notify(false);
		};
		this.setOptions(opts);
	}
	scheduleScrollReconcile() {
		if (!this.targetWindow) {
			this.scrollState = null;
			return;
		}
		if (this.rafId != null) return;
		this.rafId = this.targetWindow.requestAnimationFrame(() => {
			this.rafId = null;
			this.reconcileScroll();
		});
	}
	reconcileScroll() {
		if (!this.scrollState) return;
		if (!this.scrollElement) return;
		if (this.now() - this.scrollState.startedAt > 5e3) {
			this.scrollState = null;
			return;
		}
		const offsetInfo = this.scrollState.index != null ? this.getOffsetForIndex(this.scrollState.index, this.scrollState.align) : void 0;
		const targetOffset = offsetInfo ? offsetInfo[0] : this.scrollState.lastTargetOffset;
		const STABLE_FRAMES = 1;
		const targetChanged = targetOffset !== this.scrollState.lastTargetOffset;
		if (!targetChanged && approxEqual(targetOffset, this.getScrollOffset())) {
			this.scrollState.stableFrames++;
			if (this.scrollState.stableFrames >= STABLE_FRAMES) {
				this.scrollState = null;
				return;
			}
		} else {
			this.scrollState.stableFrames = 0;
			if (targetChanged) {
				this.scrollState.lastTargetOffset = targetOffset;
				this.scrollState.behavior = "auto";
				this._scrollToOffset(targetOffset, {
					adjustments: void 0,
					behavior: "auto"
				});
			}
		}
		this.scheduleScrollReconcile();
	}
};
var findNearestBinarySearch = (low, high, getCurrentValue, value) => {
	while (low <= high) {
		const middle = (low + high) / 2 | 0;
		const currentValue = getCurrentValue(middle);
		if (currentValue < value) low = middle + 1;
		else if (currentValue > value) high = middle - 1;
		else return middle;
	}
	if (low > 0) return low - 1;
	else return 0;
};
function calculateRange({ measurements, outerSize, scrollOffset, lanes }) {
	const lastIndex = measurements.length - 1;
	const getOffset = (index) => measurements[index].start;
	if (measurements.length <= lanes) return {
		startIndex: 0,
		endIndex: lastIndex
	};
	let startIndex = findNearestBinarySearch(0, lastIndex, getOffset, scrollOffset);
	let endIndex = startIndex;
	if (lanes === 1) while (endIndex < lastIndex && measurements[endIndex].end < scrollOffset + outerSize) endIndex++;
	else if (lanes > 1) {
		const endPerLane = Array(lanes).fill(0);
		while (endIndex < lastIndex && endPerLane.some((pos) => pos < scrollOffset + outerSize)) {
			const item = measurements[endIndex];
			endPerLane[item.lane] = item.end;
			endIndex++;
		}
		const startPerLane = Array(lanes).fill(scrollOffset + outerSize);
		while (startIndex >= 0 && startPerLane.some((pos) => pos >= scrollOffset)) {
			const item = measurements[startIndex];
			startPerLane[item.lane] = item.start;
			startIndex--;
		}
		startIndex = Math.max(0, startIndex - startIndex % lanes);
		endIndex = Math.min(lastIndex, endIndex + (lanes - 1 - endIndex % lanes));
	}
	return {
		startIndex,
		endIndex
	};
}
//#endregion
//#region node_modules/@tanstack/react-virtual/dist/esm/index.js
var useIsomorphicLayoutEffect = typeof document !== "undefined" ? import_react.useLayoutEffect : import_react.useEffect;
function useVirtualizerBase({ useFlushSync = true, ...options }) {
	const rerender = import_react.useReducer(() => ({}), {})[1];
	const resolvedOptions = {
		...options,
		onChange: (instance2, sync) => {
			var _a;
			if (useFlushSync && sync) (0, import_react_dom.flushSync)(rerender);
			else rerender();
			(_a = options.onChange) == null || _a.call(options, instance2, sync);
		}
	};
	const [instance] = import_react.useState(() => new Virtualizer(resolvedOptions));
	instance.setOptions(resolvedOptions);
	useIsomorphicLayoutEffect(() => {
		return instance._didMount();
	}, []);
	useIsomorphicLayoutEffect(() => {
		return instance._willUpdate();
	});
	return instance;
}
function useVirtualizer(options) {
	return useVirtualizerBase({
		observeElementRect,
		observeElementOffset,
		scrollToFn: elementScroll,
		...options
	});
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/env.js
var i$6 = Object.defineProperty;
var d$14 = (t, e, n) => e in t ? i$6(t, e, {
	enumerable: !0,
	configurable: !0,
	writable: !0,
	value: n
}) : t[e] = n;
var r$5 = (t, e, n) => (d$14(t, typeof e != "symbol" ? e + "" : e, n), n);
var o$11 = class {
	constructor() {
		r$5(this, "current", this.detect());
		r$5(this, "handoffState", "pending");
		r$5(this, "currentId", 0);
	}
	set(e) {
		this.current !== e && (this.handoffState = "pending", this.currentId = 0, this.current = e);
	}
	reset() {
		this.set(this.detect());
	}
	nextId() {
		return ++this.currentId;
	}
	get isServer() {
		return this.current === "server";
	}
	get isClient() {
		return this.current === "client";
	}
	detect() {
		return typeof window == "undefined" || typeof document == "undefined" ? "server" : "client";
	}
	handoff() {
		this.handoffState === "pending" && (this.handoffState = "complete");
	}
	get isHandoffComplete() {
		return this.handoffState === "complete";
	}
};
var s$14 = new o$11();
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-iso-morphic-effect.js
var l$10 = (e, f) => {
	s$14.isServer ? (0, import_react.useEffect)(e, f) : (0, import_react.useLayoutEffect)(e, f);
};
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-latest-value.js
function s$13(e) {
	let r = (0, import_react.useRef)(e);
	return l$10(() => {
		r.current = e;
	}, [e]), r;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-computed.js
function i$5(e, o) {
	let [u, t] = (0, import_react.useState)(e), r = s$13(e);
	return l$10(() => t(r.current), [
		r,
		t,
		...o
	]), u;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-event.js
var o$10 = function(t) {
	let e = s$13(t);
	return import_react.useCallback((...r) => e.current(...r), [e]);
};
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-controllable.js
function T$5(l, r, c) {
	let [i, s] = (0, import_react.useState)(c), e = l !== void 0, t = (0, import_react.useRef)(e), u = (0, import_react.useRef)(!1), d = (0, import_react.useRef)(!1);
	return e && !t.current && !u.current ? (u.current = !0, t.current = e, console.error("A component is changing from uncontrolled to controlled. This may be caused by the value changing from undefined to a defined value, which should not happen.")) : !e && t.current && !d.current && (d.current = !0, t.current = e, console.error("A component is changing from controlled to uncontrolled. This may be caused by the value changing from a defined value to undefined, which should not happen.")), [e ? l : i, o$10((n) => (e || s(n), r == null ? void 0 : r(n)))];
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/micro-task.js
function t$13(e) {
	typeof queueMicrotask == "function" ? queueMicrotask(e) : Promise.resolve().then(e).catch((o) => setTimeout(() => {
		throw o;
	}));
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/disposables.js
function o$8() {
	let n = [], r = {
		addEventListener(e, t, s, a) {
			return e.addEventListener(t, s, a), r.add(() => e.removeEventListener(t, s, a));
		},
		requestAnimationFrame(...e) {
			let t = requestAnimationFrame(...e);
			return r.add(() => cancelAnimationFrame(t));
		},
		nextFrame(...e) {
			return r.requestAnimationFrame(() => r.requestAnimationFrame(...e));
		},
		setTimeout(...e) {
			let t = setTimeout(...e);
			return r.add(() => clearTimeout(t));
		},
		microTask(...e) {
			let t = { current: !0 };
			return t$13(() => {
				t.current && e[0]();
			}), r.add(() => {
				t.current = !1;
			});
		},
		style(e, t, s) {
			let a = e.style.getPropertyValue(t);
			return Object.assign(e.style, { [t]: s }), this.add(() => {
				Object.assign(e.style, { [t]: a });
			});
		},
		group(e) {
			let t = o$8();
			return e(t), this.add(() => t.dispose());
		},
		add(e) {
			return n.push(e), () => {
				let t = n.indexOf(e);
				if (t >= 0) for (let s of n.splice(t, 1)) s();
			};
		},
		dispose() {
			for (let e of n.splice(0)) e();
		}
	};
	return r;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-disposables.js
function p$5() {
	let [e] = (0, import_react.useState)(o$8);
	return (0, import_react.useEffect)(() => () => e.dispose(), [e]), e;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-server-handoff-complete.js
function s$10() {
	let r = typeof document == "undefined";
	return "useSyncExternalStore" in import_react ? ((o) => o.useSyncExternalStore)(import_react)(() => () => {}, () => !1, () => !r) : !1;
}
function l$9() {
	let r = s$10(), [e, n] = import_react.useState(s$14.isHandoffComplete);
	return e && s$14.isHandoffComplete === !1 && n(!1), import_react.useEffect(() => {
		e !== !0 && n(!0);
	}, [e]), import_react.useEffect(() => s$14.handoff(), []), r ? !1 : e;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-id.js
var o$6;
var I$9 = (o$6 = import_react.useId) != null ? o$6 : function() {
	let n = l$9(), [e, u] = import_react.useState(n ? () => s$14.nextId() : null);
	return l$10(() => {
		e === null && u(s$14.nextId());
	}, [e]), e != null ? "" + e : void 0;
};
//#endregion
//#region node_modules/@headlessui/react/dist/utils/match.js
function u$11(r, n, ...a) {
	if (r in n) {
		let e = n[r];
		return typeof e == "function" ? e(...a) : e;
	}
	let t = /* @__PURE__ */ new Error(`Tried to handle "${r}" but there is no handler defined. Only defined handlers are: ${Object.keys(n).map((e) => `"${e}"`).join(", ")}.`);
	throw Error.captureStackTrace && Error.captureStackTrace(t, u$11), t;
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/owner.js
function o$5(r) {
	return s$14.isServer ? null : r instanceof Node ? r.ownerDocument : r != null && r.hasOwnProperty("current") && r.current instanceof Node ? r.current.ownerDocument : document;
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/focus-management.js
var c$10 = [
	"[contentEditable=true]",
	"[tabindex]",
	"a[href]",
	"area[href]",
	"button:not([disabled])",
	"iframe",
	"input:not([disabled])",
	"select:not([disabled])",
	"textarea:not([disabled])"
].map((e) => `${e}:not([tabindex='-1'])`).join(",");
var M$5 = ((n) => (n[n.First = 1] = "First", n[n.Previous = 2] = "Previous", n[n.Next = 4] = "Next", n[n.Last = 8] = "Last", n[n.WrapAround = 16] = "WrapAround", n[n.NoScroll = 32] = "NoScroll", n))(M$5 || {}), N$5 = ((o) => (o[o.Error = 0] = "Error", o[o.Overflow = 1] = "Overflow", o[o.Success = 2] = "Success", o[o.Underflow = 3] = "Underflow", o))(N$5 || {}), F$8 = ((t) => (t[t.Previous = -1] = "Previous", t[t.Next = 1] = "Next", t))(F$8 || {});
function f$11(e = document.body) {
	return e == null ? [] : Array.from(e.querySelectorAll(c$10)).sort((r, t) => Math.sign((r.tabIndex || Number.MAX_SAFE_INTEGER) - (t.tabIndex || Number.MAX_SAFE_INTEGER)));
}
var T$4 = ((t) => (t[t.Strict = 0] = "Strict", t[t.Loose = 1] = "Loose", t))(T$4 || {});
function h$7(e, r = 0) {
	var t;
	return e === ((t = o$5(e)) == null ? void 0 : t.body) ? !1 : u$11(r, {
		[0]() {
			return e.matches(c$10);
		},
		[1]() {
			let l = e;
			for (; l !== null;) {
				if (l.matches(c$10)) return !0;
				l = l.parentElement;
			}
			return !1;
		}
	});
}
function D$5(e) {
	let r = o$5(e);
	o$8().nextFrame(() => {
		r && !h$7(r.activeElement, 0) && y$5(e);
	});
}
var w$4 = ((t) => (t[t.Keyboard = 0] = "Keyboard", t[t.Mouse = 1] = "Mouse", t))(w$4 || {});
typeof window != "undefined" && typeof document != "undefined" && (document.addEventListener("keydown", (e) => {
	e.metaKey || e.altKey || e.ctrlKey || (document.documentElement.dataset.headlessuiFocusVisible = "");
}, !0), document.addEventListener("click", (e) => {
	e.detail === 1 ? delete document.documentElement.dataset.headlessuiFocusVisible : e.detail === 0 && (document.documentElement.dataset.headlessuiFocusVisible = "");
}, !0));
function y$5(e) {
	e?.focus({ preventScroll: !0 });
}
var S$8 = ["textarea", "input"].join(",");
function H$4(e) {
	var r, t;
	return (t = (r = e == null ? void 0 : e.matches) == null ? void 0 : r.call(e, S$8)) != null ? t : !1;
}
function I$8(e, r = (t) => t) {
	return e.slice().sort((t, l) => {
		let o = r(t), i = r(l);
		if (o === null || i === null) return 0;
		let n = o.compareDocumentPosition(i);
		return n & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : n & Node.DOCUMENT_POSITION_PRECEDING ? 1 : 0;
	});
}
function _$3(e, r) {
	return O$2(f$11(), r, { relativeTo: e });
}
function O$2(e, r, { sorted: t = !0, relativeTo: l = null, skipElements: o = [] } = {}) {
	let i = Array.isArray(e) ? e.length > 0 ? e[0].ownerDocument : document : e.ownerDocument, n = Array.isArray(e) ? t ? I$8(e) : e : f$11(e);
	o.length > 0 && n.length > 1 && (n = n.filter((s) => !o.includes(s))), l = l != null ? l : i.activeElement;
	let E = (() => {
		if (r & 5) return 1;
		if (r & 10) return -1;
		throw new Error("Missing Focus.First, Focus.Previous, Focus.Next or Focus.Last");
	})(), x = (() => {
		if (r & 1) return 0;
		if (r & 2) return Math.max(0, n.indexOf(l)) - 1;
		if (r & 4) return Math.max(0, n.indexOf(l)) + 1;
		if (r & 8) return n.length - 1;
		throw new Error("Missing Focus.First, Focus.Previous, Focus.Next or Focus.Last");
	})(), p = r & 32 ? { preventScroll: !0 } : {}, d = 0, a = n.length, u;
	do {
		if (d >= a || d + a <= 0) return 0;
		let s = x + d;
		if (r & 16) s = (s + a) % a;
		else {
			if (s < 0) return 3;
			if (s >= a) return 1;
		}
		u = n[s], u?.focus(p), d += E;
	} while (u !== i.activeElement);
	return r & 6 && H$4(u) && u.select(), 2;
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/platform.js
function t$11() {
	return /iPhone/gi.test(window.navigator.platform) || /Mac/gi.test(window.navigator.platform) && window.navigator.maxTouchPoints > 0;
}
function i$4() {
	return /Android/gi.test(window.navigator.userAgent);
}
function n$5() {
	return t$11() || i$4();
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-document-event.js
function d$13(e, r, n) {
	let o = s$13(r);
	(0, import_react.useEffect)(() => {
		function t(u) {
			o.current(u);
		}
		return document.addEventListener(e, t, n), () => document.removeEventListener(e, t, n);
	}, [e, n]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-window-event.js
function s$9(e, r, n) {
	let o = s$13(r);
	(0, import_react.useEffect)(() => {
		function t(i) {
			o.current(i);
		}
		return window.addEventListener(e, t, n), () => window.removeEventListener(e, t, n);
	}, [e, n]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-outside-click.js
function y$4(s, m, a = !0) {
	let i = (0, import_react.useRef)(!1);
	(0, import_react.useEffect)(() => {
		requestAnimationFrame(() => {
			i.current = a;
		});
	}, [a]);
	function c(e, r) {
		if (!i.current || e.defaultPrevented) return;
		let t = r(e);
		if (t === null || !t.getRootNode().contains(t) || !t.isConnected) return;
		let E = function u(n) {
			return typeof n == "function" ? u(n()) : Array.isArray(n) || n instanceof Set ? n : [n];
		}(s);
		for (let u of E) {
			if (u === null) continue;
			let n = u instanceof HTMLElement ? u : u.current;
			if (n != null && n.contains(t) || e.composed && e.composedPath().includes(n)) return;
		}
		return !h$7(t, T$4.Loose) && t.tabIndex !== -1 && e.preventDefault(), m(e, t);
	}
	let o = (0, import_react.useRef)(null);
	d$13("pointerdown", (e) => {
		var r, t;
		i.current && (o.current = ((t = (r = e.composedPath) == null ? void 0 : r.call(e)) == null ? void 0 : t[0]) || e.target);
	}, !0), d$13("mousedown", (e) => {
		var r, t;
		i.current && (o.current = ((t = (r = e.composedPath) == null ? void 0 : r.call(e)) == null ? void 0 : t[0]) || e.target);
	}, !0), d$13("click", (e) => {
		n$5() || o.current && (c(e, () => o.current), o.current = null);
	}, !0), d$13("touchend", (e) => c(e, () => e.target instanceof HTMLElement ? e.target : null), !0), s$9("blur", (e) => c(e, () => window.document.activeElement instanceof HTMLIFrameElement ? window.document.activeElement : null), !0);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-owner.js
function n$4(...e) {
	return (0, import_react.useMemo)(() => o$5(...e), [...e]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-resolve-button-type.js
function i$3(t) {
	var n;
	if (t.type) return t.type;
	let e = (n = t.as) != null ? n : "button";
	if (typeof e == "string" && e.toLowerCase() === "button") return "button";
}
function T$3(t, e) {
	let [n, u] = (0, import_react.useState)(() => i$3(t));
	return l$10(() => {
		u(i$3(t));
	}, [t.type, t.as]), l$10(() => {
		n || e.current && e.current instanceof HTMLButtonElement && !e.current.hasAttribute("type") && u("button");
	}, [n, e]), n;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-sync-refs.js
var u$10 = Symbol();
function T$2(t, n = !0) {
	return Object.assign(t, { [u$10]: n });
}
function y$3(...t) {
	let n = (0, import_react.useRef)(t);
	(0, import_react.useEffect)(() => {
		n.current = t;
	}, [t]);
	let c = o$10((e) => {
		for (let o of n.current) o != null && (typeof o == "function" ? o(e) : o.current = e);
	});
	return t.every((e) => e == null || (e == null ? void 0 : e[u$10])) ? void 0 : c;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-tracked-pointer.js
function t$9(e) {
	return [e.screenX, e.screenY];
}
function u$9() {
	let e = (0, import_react.useRef)([-1, -1]);
	return {
		wasMoved(r) {
			let n = t$9(r);
			return e.current[0] === n[0] && e.current[1] === n[1] ? !1 : (e.current = n, !0);
		},
		update(r) {
			e.current = t$9(r);
		}
	};
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-tree-walker.js
function F$7({ container: e, accept: t, walk: r, enabled: c = !0 }) {
	let o = (0, import_react.useRef)(t), l = (0, import_react.useRef)(r);
	(0, import_react.useEffect)(() => {
		o.current = t, l.current = r;
	}, [t, r]), l$10(() => {
		if (!e || !c) return;
		let n = o$5(e);
		if (!n) return;
		let f = o.current, p = l.current, d = Object.assign((i) => f(i), { acceptNode: f }), u = n.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, d, !1);
		for (; u.nextNode();) p(u.currentNode);
	}, [
		e,
		c,
		o,
		l
	]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-watch.js
function m$8(u, t) {
	let e = (0, import_react.useRef)([]), r = o$10(u);
	(0, import_react.useEffect)(() => {
		let o = [...e.current];
		for (let [n, a] of t.entries()) if (e.current[n] !== a) {
			let l = r(t, o);
			return e.current = t, l;
		}
	}, [r, ...t]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/class-names.js
function t$8(...r) {
	return Array.from(new Set(r.flatMap((n) => typeof n == "string" ? n.split(" ") : []))).filter(Boolean).join(" ");
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/render.js
var O$1 = ((n) => (n[n.None = 0] = "None", n[n.RenderStrategy = 1] = "RenderStrategy", n[n.Static = 2] = "Static", n))(O$1 || {}), v$4 = ((e) => (e[e.Unmount = 0] = "Unmount", e[e.Hidden = 1] = "Hidden", e))(v$4 || {});
function C$5({ ourProps: r, theirProps: t, slot: e, defaultTag: n, features: o, visible: a = !0, name: f, mergeRefs: l }) {
	l = l != null ? l : k$1;
	let s = R$2(t, r);
	if (a) return m$7(s, e, n, f, l);
	let y = o != null ? o : 0;
	if (y & 2) {
		let { static: u = !1, ...d } = s;
		if (u) return m$7(d, e, n, f, l);
	}
	if (y & 1) {
		let { unmount: u = !0, ...d } = s;
		return u$11(u ? 0 : 1, {
			[0]() {
				return null;
			},
			[1]() {
				return m$7({
					...d,
					hidden: !0,
					style: { display: "none" }
				}, e, n, f, l);
			}
		});
	}
	return m$7(s, e, n, f, l);
}
function m$7(r, t = {}, e, n, o) {
	let { as: a = e, children: f, refName: l = "ref", ...s } = F$6(r, ["unmount", "static"]), y = r.ref !== void 0 ? { [l]: r.ref } : {}, u = typeof f == "function" ? f(t) : f;
	"className" in s && s.className && typeof s.className == "function" && (s.className = s.className(t));
	let d = {};
	if (t) {
		let i = !1, c = [];
		for (let [T, p] of Object.entries(t)) typeof p == "boolean" && (i = !0), p === !0 && c.push(T);
		i && (d["data-headlessui-state"] = c.join(" "));
	}
	if (a === import_react.Fragment && Object.keys(x$2(s)).length > 0) {
		if (!(0, import_react.isValidElement)(u) || Array.isArray(u) && u.length > 1) throw new Error([
			"Passing props on \"Fragment\"!",
			"",
			`The current component <${n} /> is rendering a "Fragment".`,
			"However we need to passthrough the following props:",
			Object.keys(s).map((p) => `  - ${p}`).join(`
`),
			"",
			"You can apply a few solutions:",
			["Add an `as=\"...\"` prop, to ensure that we render an actual element instead of a \"Fragment\".", "Render a single element as the child so that we can forward the props onto that element."].map((p) => `  - ${p}`).join(`
`)
		].join(`
`));
		let i = u.props, c = typeof (i == null ? void 0 : i.className) == "function" ? (...p) => t$8(i == null ? void 0 : i.className(...p), s.className) : t$8(i == null ? void 0 : i.className, s.className), T = c ? { className: c } : {};
		return (0, import_react.cloneElement)(u, Object.assign({}, R$2(u.props, x$2(F$6(s, ["ref"]))), d, y, { ref: o(u.ref, y.ref) }, T));
	}
	return (0, import_react.createElement)(a, Object.assign({}, F$6(s, ["ref"]), a !== import_react.Fragment && y, a !== import_react.Fragment && d), u);
}
function I$7() {
	let r = (0, import_react.useRef)([]), t = (0, import_react.useCallback)((e) => {
		for (let n of r.current) n != null && (typeof n == "function" ? n(e) : n.current = e);
	}, []);
	return (...e) => {
		if (!e.every((n) => n == null)) return r.current = e, t;
	};
}
function k$1(...r) {
	return r.every((t) => t == null) ? void 0 : (t) => {
		for (let e of r) e != null && (typeof e == "function" ? e(t) : e.current = t);
	};
}
function R$2(...r) {
	if (r.length === 0) return {};
	if (r.length === 1) return r[0];
	let t = {}, e = {};
	for (let o of r) for (let a in o) a.startsWith("on") && typeof o[a] == "function" ? (e[a] ?? (e[a] = []), e[a].push(o[a])) : t[a] = o[a];
	if (t.disabled || t["aria-disabled"]) return Object.assign(t, Object.fromEntries(Object.keys(e).map((o) => [o, void 0])));
	for (let o in e) Object.assign(t, { [o](a, ...f) {
		let l = e[o];
		for (let s of l) {
			if ((a instanceof Event || (a == null ? void 0 : a.nativeEvent) instanceof Event) && a.defaultPrevented) return;
			s(a, ...f);
		}
	} });
	return t;
}
function U$5(r) {
	var t;
	return Object.assign((0, import_react.forwardRef)(r), { displayName: (t = r.displayName) != null ? t : r.name });
}
function x$2(r) {
	let t = Object.assign({}, r);
	for (let e in t) t[e] === void 0 && delete t[e];
	return t;
}
function F$6(r, t = []) {
	let e = Object.assign({}, r);
	for (let n of t) n in e && delete e[n];
	return e;
}
//#endregion
//#region node_modules/@headlessui/react/dist/internal/hidden.js
var p$4 = "div";
var s$7 = ((e) => (e[e.None = 1] = "None", e[e.Focusable = 2] = "Focusable", e[e.Hidden = 4] = "Hidden", e))(s$7 || {});
function l$7(d, o) {
	var n;
	let { features: t = 1, ...e } = d;
	return C$5({
		ourProps: {
			ref: o,
			"aria-hidden": (t & 2) === 2 ? !0 : (n = e["aria-hidden"]) != null ? n : void 0,
			hidden: (t & 4) === 4 ? !0 : void 0,
			style: {
				position: "fixed",
				top: 1,
				left: 1,
				width: 1,
				height: 0,
				padding: 0,
				margin: -1,
				overflow: "hidden",
				clip: "rect(0, 0, 0, 0)",
				whiteSpace: "nowrap",
				borderWidth: "0",
				...(t & 4) === 4 && (t & 2) !== 2 && { display: "none" }
			}
		},
		theirProps: e,
		slot: {},
		defaultTag: p$4,
		name: "Hidden"
	});
}
var u$8 = U$5(l$7);
//#endregion
//#region node_modules/@headlessui/react/dist/internal/open-closed.js
var n$3 = (0, import_react.createContext)(null);
n$3.displayName = "OpenClosedContext";
var d$10 = ((e) => (e[e.Open = 1] = "Open", e[e.Closed = 2] = "Closed", e[e.Closing = 4] = "Closing", e[e.Opening = 8] = "Opening", e))(d$10 || {});
function u$7() {
	return (0, import_react.useContext)(n$3);
}
function s$6({ value: o, children: r }) {
	return import_react.createElement(n$3.Provider, { value: o }, r);
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/document-ready.js
function t$6(n) {
	function e() {
		document.readyState !== "loading" && (n(), document.removeEventListener("DOMContentLoaded", e));
	}
	typeof window != "undefined" && typeof document != "undefined" && (document.addEventListener("DOMContentLoaded", e), e());
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/active-element-history.js
var t$5 = [];
t$6(() => {
	function e(n) {
		n.target instanceof HTMLElement && n.target !== document.body && t$5[0] !== n.target && (t$5.unshift(n.target), t$5 = t$5.filter((r) => r != null && r.isConnected), t$5.splice(10));
	}
	window.addEventListener("click", e, { capture: !0 }), window.addEventListener("mousedown", e, { capture: !0 }), window.addEventListener("focus", e, { capture: !0 }), document.body.addEventListener("click", e, { capture: !0 }), document.body.addEventListener("mousedown", e, { capture: !0 }), document.body.addEventListener("focus", e, { capture: !0 });
});
//#endregion
//#region node_modules/@headlessui/react/dist/utils/bugs.js
function r$4(n) {
	let e = n.parentElement, l = null;
	for (; e && !(e instanceof HTMLFieldSetElement);) e instanceof HTMLLegendElement && (l = e), e = e.parentElement;
	let t = (e == null ? void 0 : e.getAttribute("disabled")) === "";
	return t && i$1(l) ? !1 : t;
}
function i$1(n) {
	if (!n) return !1;
	let e = n.previousElementSibling;
	for (; e !== null;) {
		if (e instanceof HTMLLegendElement) return !1;
		e = e.previousElementSibling;
	}
	return !0;
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/calculate-active-index.js
function u$6(l) {
	throw new Error("Unexpected object: " + l);
}
var c$9 = ((i) => (i[i.First = 0] = "First", i[i.Previous = 1] = "Previous", i[i.Next = 2] = "Next", i[i.Last = 3] = "Last", i[i.Specific = 4] = "Specific", i[i.Nothing = 5] = "Nothing", i))(c$9 || {});
function f$8(l, n) {
	let t = n.resolveItems();
	if (t.length <= 0) return null;
	let r = n.resolveActiveIndex(), s = r != null ? r : -1;
	switch (l.focus) {
		case 0:
			for (let e = 0; e < t.length; ++e) if (!n.resolveDisabled(t[e], e, t)) return e;
			return r;
		case 1:
			for (let e = s - 1; e >= 0; --e) if (!n.resolveDisabled(t[e], e, t)) return e;
			return r;
		case 2:
			for (let e = s + 1; e < t.length; ++e) if (!n.resolveDisabled(t[e], e, t)) return e;
			return r;
		case 3:
			for (let e = t.length - 1; e >= 0; --e) if (!n.resolveDisabled(t[e], e, t)) return e;
			return r;
		case 4:
			for (let e = 0; e < t.length; ++e) if (n.resolveId(t[e], e, t) === l.id) return e;
			return r;
		case 5: return null;
		default: u$6(l);
	}
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/form.js
function e$1(i = {}, s = null, t = []) {
	for (let [r, n] of Object.entries(i)) o$2(t, f$7(s, r), n);
	return t;
}
function f$7(i, s) {
	return i ? i + "[" + s + "]" : s;
}
function o$2(i, s, t) {
	if (Array.isArray(t)) for (let [r, n] of t.entries()) o$2(i, f$7(s, r.toString()), n);
	else t instanceof Date ? i.push([s, t.toISOString()]) : typeof t == "boolean" ? i.push([s, t ? "1" : "0"]) : typeof t == "string" ? i.push([s, t]) : typeof t == "number" ? i.push([s, `${t}`]) : t == null ? i.push([s, ""]) : e$1(t, s, i);
}
function p$2(i) {
	var t, r;
	let s = (t = i == null ? void 0 : i.form) != null ? t : i.closest("form");
	if (s) {
		for (let n of s.elements) if (n !== i && (n.tagName === "INPUT" && n.type === "submit" || n.tagName === "BUTTON" && n.type === "submit" || n.nodeName === "INPUT" && n.type === "image")) {
			n.click();
			return;
		}
		(r = s.requestSubmit) == null || r.call(s);
	}
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/keyboard.js
var o$1 = ((r) => (r.Space = " ", r.Enter = "Enter", r.Escape = "Escape", r.Backspace = "Backspace", r.Delete = "Delete", r.ArrowLeft = "ArrowLeft", r.ArrowUp = "ArrowUp", r.ArrowRight = "ArrowRight", r.ArrowDown = "ArrowDown", r.Home = "Home", r.End = "End", r.PageUp = "PageUp", r.PageDown = "PageDown", r.Tab = "Tab", r))(o$1 || {});
//#endregion
//#region node_modules/@headlessui/react/dist/components/combobox/combobox.js
var $e$4 = ((o) => (o[o.Open = 0] = "Open", o[o.Closed = 1] = "Closed", o))($e$4 || {}), qe$5 = ((o) => (o[o.Single = 0] = "Single", o[o.Multi = 1] = "Multi", o))(qe$5 || {}), ze$3 = ((a) => (a[a.Pointer = 0] = "Pointer", a[a.Focus = 1] = "Focus", a[a.Other = 2] = "Other", a))(ze$3 || {}), Ye$3 = ((e) => (e[e.OpenCombobox = 0] = "OpenCombobox", e[e.CloseCombobox = 1] = "CloseCombobox", e[e.GoToOption = 2] = "GoToOption", e[e.RegisterOption = 3] = "RegisterOption", e[e.UnregisterOption = 4] = "UnregisterOption", e[e.RegisterLabel = 5] = "RegisterLabel", e[e.SetActivationTrigger = 6] = "SetActivationTrigger", e[e.UpdateVirtualOptions = 7] = "UpdateVirtualOptions", e))(Ye$3 || {});
function de$4(t, r = (o) => o) {
	let o = t.activeOptionIndex !== null ? t.options[t.activeOptionIndex] : null, a = r(t.options.slice()), i = a.length > 0 && a[0].dataRef.current.order !== null ? a.sort((p, c) => p.dataRef.current.order - c.dataRef.current.order) : I$8(a, (p) => p.dataRef.current.domRef.current), u = o ? i.indexOf(o) : null;
	return u === -1 && (u = null), {
		options: i,
		activeOptionIndex: u
	};
}
var Qe$3 = {
	[1](t) {
		var r;
		return (r = t.dataRef.current) != null && r.disabled || t.comboboxState === 1 ? t : {
			...t,
			activeOptionIndex: null,
			comboboxState: 1
		};
	},
	[0](t) {
		var r, o;
		if ((r = t.dataRef.current) != null && r.disabled || t.comboboxState === 0) return t;
		if ((o = t.dataRef.current) != null && o.value) {
			let a = t.dataRef.current.calculateIndex(t.dataRef.current.value);
			if (a !== -1) return {
				...t,
				activeOptionIndex: a,
				comboboxState: 0
			};
		}
		return {
			...t,
			comboboxState: 0
		};
	},
	[2](t, r) {
		var u, p, c, e, l;
		if ((u = t.dataRef.current) != null && u.disabled || (p = t.dataRef.current) != null && p.optionsRef.current && !((c = t.dataRef.current) != null && c.optionsPropsRef.current.static) && t.comboboxState === 1) return t;
		if (t.virtual) {
			let T = r.focus === c$9.Specific ? r.idx : f$8(r, {
				resolveItems: () => t.virtual.options,
				resolveActiveIndex: () => {
					var f, v;
					return (v = (f = t.activeOptionIndex) != null ? f : t.virtual.options.findIndex((S) => !t.virtual.disabled(S))) != null ? v : null;
				},
				resolveDisabled: t.virtual.disabled,
				resolveId() {
					throw new Error("Function not implemented.");
				}
			}), g = (e = r.trigger) != null ? e : 2;
			return t.activeOptionIndex === T && t.activationTrigger === g ? t : {
				...t,
				activeOptionIndex: T,
				activationTrigger: g
			};
		}
		let o = de$4(t);
		if (o.activeOptionIndex === null) {
			let T = o.options.findIndex((g) => !g.dataRef.current.disabled);
			T !== -1 && (o.activeOptionIndex = T);
		}
		let a = r.focus === c$9.Specific ? r.idx : f$8(r, {
			resolveItems: () => o.options,
			resolveActiveIndex: () => o.activeOptionIndex,
			resolveId: (T) => T.id,
			resolveDisabled: (T) => T.dataRef.current.disabled
		}), i = (l = r.trigger) != null ? l : 2;
		return t.activeOptionIndex === a && t.activationTrigger === i ? t : {
			...t,
			...o,
			activeOptionIndex: a,
			activationTrigger: i
		};
	},
	[3]: (t, r) => {
		var u, p, c;
		if ((u = t.dataRef.current) != null && u.virtual) return {
			...t,
			options: [...t.options, r.payload]
		};
		let o = r.payload, a = de$4(t, (e) => (e.push(o), e));
		t.activeOptionIndex === null && (p = t.dataRef.current) != null && p.isSelected(r.payload.dataRef.current.value) && (a.activeOptionIndex = a.options.indexOf(o));
		let i = {
			...t,
			...a,
			activationTrigger: 2
		};
		return (c = t.dataRef.current) != null && c.__demoMode && t.dataRef.current.value === void 0 && (i.activeOptionIndex = 0), i;
	},
	[4]: (t, r) => {
		var a;
		if ((a = t.dataRef.current) != null && a.virtual) return {
			...t,
			options: t.options.filter((i) => i.id !== r.id)
		};
		let o = de$4(t, (i) => {
			let u = i.findIndex((p) => p.id === r.id);
			return u !== -1 && i.splice(u, 1), i;
		});
		return {
			...t,
			...o,
			activationTrigger: 2
		};
	},
	[5]: (t, r) => t.labelId === r.id ? t : {
		...t,
		labelId: r.id
	},
	[6]: (t, r) => t.activationTrigger === r.trigger ? t : {
		...t,
		activationTrigger: r.trigger
	},
	[7]: (t, r) => {
		var a;
		if (((a = t.virtual) == null ? void 0 : a.options) === r.options) return t;
		let o = t.activeOptionIndex;
		if (t.activeOptionIndex !== null) {
			let i = r.options.indexOf(t.virtual.options[t.activeOptionIndex]);
			i !== -1 ? o = i : o = null;
		}
		return {
			...t,
			activeOptionIndex: o,
			virtual: Object.assign({}, t.virtual, { options: r.options })
		};
	}
}, be$2 = (0, import_react.createContext)(null);
be$2.displayName = "ComboboxActionsContext";
function ee$6(t) {
	let r = (0, import_react.useContext)(be$2);
	if (r === null) {
		let o = /* @__PURE__ */ new Error(`<${t} /> is missing a parent <Combobox /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(o, ee$6), o;
	}
	return r;
}
var Ce$1 = (0, import_react.createContext)(null);
function Ze$3(t) {
	var c;
	let r = j$2("VirtualProvider"), [o, a] = (0, import_react.useMemo)(() => {
		let e = r.optionsRef.current;
		if (!e) return [0, 0];
		let l = window.getComputedStyle(e);
		return [parseFloat(l.paddingBlockStart || l.paddingTop), parseFloat(l.paddingBlockEnd || l.paddingBottom)];
	}, [r.optionsRef.current]), i = useVirtualizer({
		scrollPaddingStart: o,
		scrollPaddingEnd: a,
		count: r.virtual.options.length,
		estimateSize() {
			return 40;
		},
		getScrollElement() {
			var e;
			return (e = r.optionsRef.current) != null ? e : null;
		},
		overscan: 12
	}), [u, p] = (0, import_react.useState)(0);
	return l$10(() => {
		p((e) => e + 1);
	}, [(c = r.virtual) == null ? void 0 : c.options]), import_react.createElement(Ce$1.Provider, { value: i }, import_react.createElement("div", {
		style: {
			position: "relative",
			width: "100%",
			height: `${i.getTotalSize()}px`
		},
		ref: (e) => {
			if (e) {
				if (typeof process != "undefined" && process.env.JEST_WORKER_ID !== void 0 || r.activationTrigger === 0) return;
				r.activeOptionIndex !== null && r.virtual.options.length > r.activeOptionIndex && i.scrollToIndex(r.activeOptionIndex);
			}
		}
	}, i.getVirtualItems().map((e) => {
		var l;
		return import_react.createElement(import_react.Fragment, { key: e.key }, import_react.cloneElement((l = t.children) == null ? void 0 : l.call(t, {
			option: r.virtual.options[e.index],
			open: r.comboboxState === 0
		}), {
			key: `${u}-${e.key}`,
			"data-index": e.index,
			"aria-setsize": r.virtual.options.length,
			"aria-posinset": e.index + 1,
			style: {
				position: "absolute",
				top: 0,
				left: 0,
				transform: `translateY(${e.start}px)`,
				overflowAnchor: "none"
			}
		}));
	})));
}
var ce$2 = (0, import_react.createContext)(null);
ce$2.displayName = "ComboboxDataContext";
function j$2(t) {
	let r = (0, import_react.useContext)(ce$2);
	if (r === null) {
		let o = /* @__PURE__ */ new Error(`<${t} /> is missing a parent <Combobox /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(o, j$2), o;
	}
	return r;
}
function et$3(t, r) {
	return u$11(r.type, Qe$3, t, r);
}
var tt$3 = import_react.Fragment;
function ot$2(t, r) {
	let { value: o, defaultValue: a, onChange: i, form: u, name: p, by: c = null, disabled: e = !1, __demoMode: l = !1, nullable: T = !1, multiple: g = !1, immediate: f = !1, virtual: v = null, ...S } = t, R = !1, s = null, [I = g ? [] : void 0, V] = T$5(o, i, a), [_, E] = (0, import_react.useReducer)(et$3, {
		dataRef: (0, import_react.createRef)(),
		comboboxState: l ? 0 : 1,
		options: [],
		virtual: null,
		activeOptionIndex: null,
		activationTrigger: 2,
		labelId: null
	}), k = (0, import_react.useRef)(!1), J = (0, import_react.useRef)({
		static: !1,
		hold: !1
	}), K = (0, import_react.useRef)(null), z = (0, import_react.useRef)(null), te = (0, import_react.useRef)(null), X = (0, import_react.useRef)(null), x = o$10(typeof c == "string" ? (d, b) => {
		let P = c;
		return (d == null ? void 0 : d[P]) === (b == null ? void 0 : b[P]);
	} : c != null ? c : (d, b) => d === b), O = o$10((d) => _.options.findIndex((b) => x(b.dataRef.current.value, d))), L = (0, import_react.useCallback)((d) => u$11(n.mode, {
		[1]: () => I.some((b) => x(b, d)),
		[0]: () => x(I, d)
	}), [I]), oe = o$10((d) => _.activeOptionIndex === O(d)), n = (0, import_react.useMemo)(() => ({
		..._,
		immediate: R,
		optionsPropsRef: J,
		labelRef: K,
		inputRef: z,
		buttonRef: te,
		optionsRef: X,
		value: I,
		defaultValue: a,
		disabled: e,
		mode: g ? 1 : 0,
		virtual: _.virtual,
		get activeOptionIndex() {
			if (k.current && _.activeOptionIndex === null && _.options.length > 0) {
				let d = _.options.findIndex((b) => !b.dataRef.current.disabled);
				if (d !== -1) return d;
			}
			return _.activeOptionIndex;
		},
		calculateIndex: O,
		compare: x,
		isSelected: L,
		isActive: oe,
		nullable: T,
		__demoMode: l
	}), [
		I,
		a,
		e,
		g,
		T,
		l,
		_,
		s
	]);
	l$10(() => {}, [s, void 0]), l$10(() => {
		_.dataRef.current = n;
	}, [n]), y$4([
		n.buttonRef,
		n.inputRef,
		n.optionsRef
	], () => le.closeCombobox(), n.comboboxState === 0);
	let F = (0, import_react.useMemo)(() => {
		var d, b, P;
		return {
			open: n.comboboxState === 0,
			disabled: e,
			activeIndex: n.activeOptionIndex,
			activeOption: n.activeOptionIndex === null ? null : n.virtual ? n.virtual.options[(d = n.activeOptionIndex) != null ? d : 0] : (P = (b = n.options[n.activeOptionIndex]) == null ? void 0 : b.dataRef.current.value) != null ? P : null,
			value: I
		};
	}, [
		n,
		e,
		I
	]), A = o$10(() => {
		if (n.activeOptionIndex !== null) {
			if (n.virtual) ae(n.virtual.options[n.activeOptionIndex]);
			else {
				let { dataRef: d } = n.options[n.activeOptionIndex];
				ae(d.current.value);
			}
			le.goToOption(c$9.Specific, n.activeOptionIndex);
		}
	}), h = o$10(() => {
		E({ type: 0 }), k.current = !0;
	}), C = o$10(() => {
		E({ type: 1 }), k.current = !1;
	}), D = o$10((d, b, P) => (k.current = !1, d === c$9.Specific ? E({
		type: 2,
		focus: c$9.Specific,
		idx: b,
		trigger: P
	}) : E({
		type: 2,
		focus: d,
		trigger: P
	}))), N = o$10((d, b) => (E({
		type: 3,
		payload: {
			id: d,
			dataRef: b
		}
	}), () => {
		n.isActive(b.current.value) && (k.current = !0), E({
			type: 4,
			id: d
		});
	})), ye = o$10((d) => (E({
		type: 5,
		id: d
	}), () => E({
		type: 5,
		id: null
	}))), ae = o$10((d) => u$11(n.mode, {
		[0]() {
			return V == null ? void 0 : V(d);
		},
		[1]() {
			let b = n.value.slice(), P = b.findIndex((G) => x(G, d));
			return P === -1 ? b.push(d) : b.splice(P, 1), V == null ? void 0 : V(b);
		}
	})), Re = o$10((d) => {
		E({
			type: 6,
			trigger: d
		});
	}), le = (0, import_react.useMemo)(() => ({
		onChange: ae,
		registerOption: N,
		registerLabel: ye,
		goToOption: D,
		closeCombobox: C,
		openCombobox: h,
		setActivationTrigger: Re,
		selectActiveOption: A
	}), []), Ae = r === null ? {} : { ref: r }, ne = (0, import_react.useRef)(null), Se = p$5();
	return (0, import_react.useEffect)(() => {
		ne.current && a !== void 0 && Se.addEventListener(ne.current, "reset", () => {
			V?.(a);
		});
	}, [ne, V]), import_react.createElement(be$2.Provider, { value: le }, import_react.createElement(ce$2.Provider, { value: n }, import_react.createElement(s$6, { value: u$11(n.comboboxState, {
		[0]: d$10.Open,
		[1]: d$10.Closed
	}) }, p != null && I != null && e$1({ [p]: I }).map(([d, b], P) => import_react.createElement(u$8, {
		features: s$7.Hidden,
		ref: P === 0 ? (G) => {
			var Y;
			ne.current = (Y = G == null ? void 0 : G.closest("form")) != null ? Y : null;
		} : void 0,
		...x$2({
			key: d,
			as: "input",
			type: "hidden",
			hidden: !0,
			readOnly: !0,
			form: u,
			disabled: e,
			name: d,
			value: b
		})
	})), C$5({
		ourProps: Ae,
		theirProps: S,
		slot: F,
		defaultTag: tt$3,
		name: "Combobox"
	}))));
}
var nt$1 = "input";
function rt$1(t, r) {
	var X, x, O, L, oe;
	let o = I$9(), { id: a = `headlessui-combobox-input-${o}`, onChange: i, displayValue: u, type: p = "text", ...c } = t, e = j$2("Combobox.Input"), l = ee$6("Combobox.Input"), T = y$3(e.inputRef, r), g = n$4(e.inputRef), f = (0, import_react.useRef)(!1), v = p$5(), S = o$10(() => {
		l.onChange(null), e.optionsRef.current && (e.optionsRef.current.scrollTop = 0), l.goToOption(c$9.Nothing);
	});
	m$8(([n, F], [A, h]) => {
		if (f.current) return;
		let C = e.inputRef.current;
		C && ((h === 0 && F === 1 || n !== A) && (C.value = n), requestAnimationFrame(() => {
			if (f.current || !C || (g == null ? void 0 : g.activeElement) !== C) return;
			let { selectionStart: D, selectionEnd: N } = C;
			Math.abs((N != null ? N : 0) - (D != null ? D : 0)) === 0 && D === 0 && C.setSelectionRange(C.value.length, C.value.length);
		}));
	}, [
		function() {
			var n;
			return typeof u == "function" && e.value !== void 0 ? (n = u(e.value)) != null ? n : "" : typeof e.value == "string" ? e.value : "";
		}(),
		e.comboboxState,
		g
	]), m$8(([n], [F]) => {
		if (n === 0 && F === 1) {
			if (f.current) return;
			let A = e.inputRef.current;
			if (!A) return;
			let h = A.value, { selectionStart: C, selectionEnd: D, selectionDirection: N } = A;
			A.value = "", A.value = h, N !== null ? A.setSelectionRange(C, D, N) : A.setSelectionRange(C, D);
		}
	}, [e.comboboxState]);
	let s = (0, import_react.useRef)(!1), I = o$10(() => {
		s.current = !0;
	}), V = o$10(() => {
		v.nextFrame(() => {
			s.current = !1;
		});
	}), _ = o$10((n) => {
		switch (f.current = !0, n.key) {
			case o$1.Enter:
				if (f.current = !1, e.comboboxState !== 0 || s.current) return;
				if (n.preventDefault(), n.stopPropagation(), e.activeOptionIndex === null) {
					l.closeCombobox();
					return;
				}
				l.selectActiveOption(), e.mode === 0 && l.closeCombobox();
				break;
			case o$1.ArrowDown: return f.current = !1, n.preventDefault(), n.stopPropagation(), u$11(e.comboboxState, {
				[0]: () => l.goToOption(c$9.Next),
				[1]: () => l.openCombobox()
			});
			case o$1.ArrowUp: return f.current = !1, n.preventDefault(), n.stopPropagation(), u$11(e.comboboxState, {
				[0]: () => l.goToOption(c$9.Previous),
				[1]: () => {
					l.openCombobox(), v.nextFrame(() => {
						e.value || l.goToOption(c$9.Last);
					});
				}
			});
			case o$1.Home:
				if (n.shiftKey) break;
				return f.current = !1, n.preventDefault(), n.stopPropagation(), l.goToOption(c$9.First);
			case o$1.PageUp: return f.current = !1, n.preventDefault(), n.stopPropagation(), l.goToOption(c$9.First);
			case o$1.End:
				if (n.shiftKey) break;
				return f.current = !1, n.preventDefault(), n.stopPropagation(), l.goToOption(c$9.Last);
			case o$1.PageDown: return f.current = !1, n.preventDefault(), n.stopPropagation(), l.goToOption(c$9.Last);
			case o$1.Escape: return f.current = !1, e.comboboxState !== 0 ? void 0 : (n.preventDefault(), e.optionsRef.current && !e.optionsPropsRef.current.static && n.stopPropagation(), e.nullable && e.mode === 0 && e.value === null && S(), l.closeCombobox());
			case o$1.Tab:
				if (f.current = !1, e.comboboxState !== 0) return;
				e.mode === 0 && e.activationTrigger !== 1 && l.selectActiveOption(), l.closeCombobox();
				break;
		}
	}), E = o$10((n) => {
		i?.(n), e.nullable && e.mode === 0 && n.target.value === "" && S(), l.openCombobox();
	}), k = o$10((n) => {
		var A, h, C;
		let F = (A = n.relatedTarget) != null ? A : t$5.find((D) => D !== n.currentTarget);
		if (f.current = !1, !((h = e.optionsRef.current) != null && h.contains(F)) && !((C = e.buttonRef.current) != null && C.contains(F)) && e.comboboxState === 0) return n.preventDefault(), e.mode === 0 && (e.nullable && e.value === null ? S() : e.activationTrigger !== 1 && l.selectActiveOption()), l.closeCombobox();
	}), J = o$10((n) => {
		var A, h, C;
		let F = (A = n.relatedTarget) != null ? A : t$5.find((D) => D !== n.currentTarget);
		(h = e.buttonRef.current) != null && h.contains(F) || (C = e.optionsRef.current) != null && C.contains(F) || e.disabled || e.immediate && e.comboboxState !== 0 && (l.openCombobox(), v.nextFrame(() => {
			l.setActivationTrigger(1);
		}));
	}), K = i$5(() => {
		if (e.labelId) return [e.labelId].join(" ");
	}, [e.labelId]), z = (0, import_react.useMemo)(() => ({
		open: e.comboboxState === 0,
		disabled: e.disabled
	}), [e]);
	return C$5({
		ourProps: {
			ref: T,
			id: a,
			role: "combobox",
			type: p,
			"aria-controls": (X = e.optionsRef.current) == null ? void 0 : X.id,
			"aria-expanded": e.comboboxState === 0,
			"aria-activedescendant": e.activeOptionIndex === null ? void 0 : e.virtual ? (x = e.options.find((n) => {
				var F;
				return !((F = e.virtual) != null && F.disabled(n.dataRef.current.value)) && e.compare(n.dataRef.current.value, e.virtual.options[e.activeOptionIndex]);
			})) == null ? void 0 : x.id : (O = e.options[e.activeOptionIndex]) == null ? void 0 : O.id,
			"aria-labelledby": K,
			"aria-autocomplete": "list",
			defaultValue: (oe = (L = t.defaultValue) != null ? L : e.defaultValue !== void 0 ? u == null ? void 0 : u(e.defaultValue) : null) != null ? oe : e.defaultValue,
			disabled: e.disabled,
			onCompositionStart: I,
			onCompositionEnd: V,
			onKeyDown: _,
			onChange: E,
			onFocus: J,
			onBlur: k
		},
		theirProps: c,
		slot: z,
		defaultTag: nt$1,
		name: "Combobox.Input"
	});
}
var at = "button";
function lt(t, r) {
	var S;
	let o = j$2("Combobox.Button"), a = ee$6("Combobox.Button"), i = y$3(o.buttonRef, r), u = I$9(), { id: p = `headlessui-combobox-button-${u}`, ...c } = t, e = p$5(), l = o$10((R) => {
		switch (R.key) {
			case o$1.ArrowDown: return R.preventDefault(), R.stopPropagation(), o.comboboxState === 1 && a.openCombobox(), e.nextFrame(() => {
				var s;
				return (s = o.inputRef.current) == null ? void 0 : s.focus({ preventScroll: !0 });
			});
			case o$1.ArrowUp: return R.preventDefault(), R.stopPropagation(), o.comboboxState === 1 && (a.openCombobox(), e.nextFrame(() => {
				o.value || a.goToOption(c$9.Last);
			})), e.nextFrame(() => {
				var s;
				return (s = o.inputRef.current) == null ? void 0 : s.focus({ preventScroll: !0 });
			});
			case o$1.Escape: return o.comboboxState !== 0 ? void 0 : (R.preventDefault(), o.optionsRef.current && !o.optionsPropsRef.current.static && R.stopPropagation(), a.closeCombobox(), e.nextFrame(() => {
				var s;
				return (s = o.inputRef.current) == null ? void 0 : s.focus({ preventScroll: !0 });
			}));
			default: return;
		}
	}), T = o$10((R) => {
		if (r$4(R.currentTarget)) return R.preventDefault();
		o.comboboxState === 0 ? a.closeCombobox() : (R.preventDefault(), a.openCombobox()), e.nextFrame(() => {
			var s;
			return (s = o.inputRef.current) == null ? void 0 : s.focus({ preventScroll: !0 });
		});
	}), g = i$5(() => {
		if (o.labelId) return [o.labelId, p].join(" ");
	}, [o.labelId, p]), f = (0, import_react.useMemo)(() => ({
		open: o.comboboxState === 0,
		disabled: o.disabled,
		value: o.value
	}), [o]);
	return C$5({
		ourProps: {
			ref: i,
			id: p,
			type: T$3(t, o.buttonRef),
			tabIndex: -1,
			"aria-haspopup": "listbox",
			"aria-controls": (S = o.optionsRef.current) == null ? void 0 : S.id,
			"aria-expanded": o.comboboxState === 0,
			"aria-labelledby": g,
			disabled: o.disabled,
			onClick: T,
			onKeyDown: l
		},
		theirProps: c,
		slot: f,
		defaultTag: at,
		name: "Combobox.Button"
	});
}
var it$2 = "label";
function ut(t, r) {
	let o = I$9(), { id: a = `headlessui-combobox-label-${o}`, ...i } = t, u = j$2("Combobox.Label"), p = ee$6("Combobox.Label"), c = y$3(u.labelRef, r);
	l$10(() => p.registerLabel(a), [a]);
	let e = o$10(() => {
		var g;
		return (g = u.inputRef.current) == null ? void 0 : g.focus({ preventScroll: !0 });
	}), l = (0, import_react.useMemo)(() => ({
		open: u.comboboxState === 0,
		disabled: u.disabled
	}), [u]);
	return C$5({
		ourProps: {
			ref: c,
			id: a,
			onClick: e
		},
		theirProps: i,
		slot: l,
		defaultTag: it$2,
		name: "Combobox.Label"
	});
}
var pt = "ul", st = O$1.RenderStrategy | O$1.Static;
function dt(t, r) {
	let o = I$9(), { id: a = `headlessui-combobox-options-${o}`, hold: i = !1, ...u } = t, p = j$2("Combobox.Options"), c = y$3(p.optionsRef, r), e = u$7(), l = (() => e !== null ? (e & d$10.Open) === d$10.Open : p.comboboxState === 0)();
	l$10(() => {
		var v;
		p.optionsPropsRef.current.static = (v = t.static) != null ? v : !1;
	}, [p.optionsPropsRef, t.static]), l$10(() => {
		p.optionsPropsRef.current.hold = i;
	}, [p.optionsPropsRef, i]), F$7({
		container: p.optionsRef.current,
		enabled: p.comboboxState === 0,
		accept(v) {
			return v.getAttribute("role") === "option" ? NodeFilter.FILTER_REJECT : v.hasAttribute("role") ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT;
		},
		walk(v) {
			v.setAttribute("role", "none");
		}
	});
	let T = i$5(() => {
		var v, S;
		return (S = p.labelId) != null ? S : (v = p.buttonRef.current) == null ? void 0 : v.id;
	}, [p.labelId, p.buttonRef.current]), g = (0, import_react.useMemo)(() => ({
		open: p.comboboxState === 0,
		option: void 0
	}), [p]), f = {
		"aria-labelledby": T,
		role: "listbox",
		"aria-multiselectable": p.mode === 1 ? !0 : void 0,
		id: a,
		ref: c
	};
	return p.virtual && p.comboboxState === 0 && Object.assign(u, { children: import_react.createElement(Ze$3, null, u.children) }), C$5({
		ourProps: f,
		theirProps: u,
		slot: g,
		defaultTag: pt,
		features: st,
		visible: l,
		name: "Combobox.Options"
	});
}
var bt = "li";
function ct(t, r) {
	var X;
	let o = I$9(), { id: a = `headlessui-combobox-option-${o}`, disabled: i = !1, value: u, order: p = null, ...c } = t, e = j$2("Combobox.Option"), l = ee$6("Combobox.Option"), T = e.virtual ? e.activeOptionIndex === e.calculateIndex(u) : e.activeOptionIndex === null ? !1 : ((X = e.options[e.activeOptionIndex]) == null ? void 0 : X.id) === a, g = e.isSelected(u), f = (0, import_react.useRef)(null), v = s$13({
		disabled: i,
		value: u,
		domRef: f,
		order: p
	}), S = (0, import_react.useContext)(Ce$1), R = y$3(r, f, S ? S.measureElement : null), s = o$10(() => l.onChange(u));
	l$10(() => l.registerOption(a, v), [v, a]);
	let I = (0, import_react.useRef)(!(e.virtual || e.__demoMode));
	l$10(() => {
		if (!e.virtual || !e.__demoMode) return;
		let x = o$8();
		return x.requestAnimationFrame(() => {
			I.current = !0;
		}), x.dispose;
	}, [e.virtual, e.__demoMode]), l$10(() => {
		if (!I.current || e.comboboxState !== 0 || !T || e.activationTrigger === 0) return;
		let x = o$8();
		return x.requestAnimationFrame(() => {
			var O, L;
			(L = (O = f.current) == null ? void 0 : O.scrollIntoView) == null || L.call(O, { block: "nearest" });
		}), x.dispose;
	}, [
		f,
		T,
		e.comboboxState,
		e.activationTrigger,
		e.activeOptionIndex
	]);
	let V = o$10((x) => {
		var O;
		if (i || (O = e.virtual) != null && O.disabled(u)) return x.preventDefault();
		s(), n$5() || requestAnimationFrame(() => {
			var L;
			return (L = e.inputRef.current) == null ? void 0 : L.focus({ preventScroll: !0 });
		}), e.mode === 0 && requestAnimationFrame(() => l.closeCombobox());
	}), _ = o$10(() => {
		var O;
		if (i || (O = e.virtual) != null && O.disabled(u)) return l.goToOption(c$9.Nothing);
		let x = e.calculateIndex(u);
		l.goToOption(c$9.Specific, x);
	}), E = u$9(), k = o$10((x) => E.update(x)), J = o$10((x) => {
		var L;
		if (!E.wasMoved(x) || i || (L = e.virtual) != null && L.disabled(u) || T) return;
		let O = e.calculateIndex(u);
		l.goToOption(c$9.Specific, O, 0);
	}), K = o$10((x) => {
		var O;
		E.wasMoved(x) && (i || (O = e.virtual) != null && O.disabled(u) || T && (e.optionsPropsRef.current.hold || l.goToOption(c$9.Nothing)));
	}), z = (0, import_react.useMemo)(() => ({
		active: T,
		selected: g,
		disabled: i
	}), [
		T,
		g,
		i
	]);
	return C$5({
		ourProps: {
			id: a,
			ref: R,
			role: "option",
			tabIndex: i === !0 ? void 0 : -1,
			"aria-disabled": i === !0 ? !0 : void 0,
			"aria-selected": g,
			disabled: void 0,
			onClick: V,
			onFocus: _,
			onPointerEnter: k,
			onMouseEnter: k,
			onPointerMove: J,
			onMouseMove: J,
			onPointerLeave: K,
			onMouseLeave: K
		},
		theirProps: c,
		slot: z,
		defaultTag: bt,
		name: "Combobox.Option"
	});
}
var ft = U$5(ot$2), mt = U$5(lt), Tt = U$5(rt$1), xt = U$5(ut), gt = U$5(dt), vt = U$5(ct), qt = Object.assign(ft, {
	Input: Tt,
	Button: mt,
	Label: xt,
	Options: gt,
	Option: vt
});
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-event-listener.js
function E$4(n, e, a, t) {
	let i = s$13(a);
	(0, import_react.useEffect)(() => {
		n = n != null ? n : window;
		function r(o) {
			i.current(o);
		}
		return n.addEventListener(e, r, t), () => n.removeEventListener(e, r, t);
	}, [
		n,
		e,
		t
	]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-is-mounted.js
function f$6() {
	let e = (0, import_react.useRef)(!1);
	return l$10(() => (e.current = !0, () => {
		e.current = !1;
	}), []), e;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-on-unmount.js
function c$8(t) {
	let r = o$10(t), e = (0, import_react.useRef)(!1);
	(0, import_react.useEffect)(() => (e.current = !1, () => {
		e.current = !0, t$13(() => {
			e.current && r();
		});
	}), [r]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-tab-direction.js
var s$5 = ((r) => (r[r.Forwards = 0] = "Forwards", r[r.Backwards = 1] = "Backwards", r))(s$5 || {});
function n$1() {
	let e = (0, import_react.useRef)(0);
	return s$9("keydown", (o) => {
		o.key === "Tab" && (e.current = o.shiftKey ? 1 : 0);
	}, !0), e;
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/focus-trap/focus-trap.js
function P$2(t) {
	if (!t) return /* @__PURE__ */ new Set();
	if (typeof t == "function") return new Set(t());
	let n = /* @__PURE__ */ new Set();
	for (let e of t.current) e.current instanceof HTMLElement && n.add(e.current);
	return n;
}
var X$3 = "div";
var _$2 = ((r) => (r[r.None = 1] = "None", r[r.InitialFocus = 2] = "InitialFocus", r[r.TabLock = 4] = "TabLock", r[r.FocusLock = 8] = "FocusLock", r[r.RestoreFocus = 16] = "RestoreFocus", r[r.All = 30] = "All", r))(_$2 || {});
function z$2(t, n) {
	let e = (0, import_react.useRef)(null), o = y$3(e, n), { initialFocus: l, containers: c, features: r = 30, ...s } = t;
	l$9() || (r = 1);
	let i = n$4(e);
	Y$1({ ownerDocument: i }, Boolean(r & 16));
	$$4({
		ownerDocument: i,
		container: e,
		containers: c,
		previousActiveElement: Z$4({
			ownerDocument: i,
			container: e,
			initialFocus: l
		}, Boolean(r & 2))
	}, Boolean(r & 8));
	let y = n$1(), R = o$10((a) => {
		let m = e.current;
		if (!m) return;
		((B) => B())(() => {
			u$11(y.current, {
				[s$5.Forwards]: () => {
					O$2(m, M$5.First, { skipElements: [a.relatedTarget] });
				},
				[s$5.Backwards]: () => {
					O$2(m, M$5.Last, { skipElements: [a.relatedTarget] });
				}
			});
		});
	}), h = p$5(), H = (0, import_react.useRef)(!1), j = {
		ref: o,
		onKeyDown(a) {
			a.key == "Tab" && (H.current = !0, h.requestAnimationFrame(() => {
				H.current = !1;
			}));
		},
		onBlur(a) {
			let m = P$2(c);
			e.current instanceof HTMLElement && m.add(e.current);
			let T = a.relatedTarget;
			T instanceof HTMLElement && T.dataset.headlessuiFocusGuard !== "true" && (S$6(m, T) || (H.current ? O$2(e.current, u$11(y.current, {
				[s$5.Forwards]: () => M$5.Next,
				[s$5.Backwards]: () => M$5.Previous
			}) | M$5.WrapAround, { relativeTo: a.target }) : a.target instanceof HTMLElement && y$5(a.target)));
		}
	};
	return import_react.createElement(import_react.Fragment, null, Boolean(r & 4) && import_react.createElement(u$8, {
		as: "button",
		type: "button",
		"data-headlessui-focus-guard": !0,
		onFocus: R,
		features: s$7.Focusable
	}), C$5({
		ourProps: j,
		theirProps: s,
		defaultTag: X$3,
		name: "FocusTrap"
	}), Boolean(r & 4) && import_react.createElement(u$8, {
		as: "button",
		type: "button",
		"data-headlessui-focus-guard": !0,
		onFocus: R,
		features: s$7.Focusable
	}));
}
var D$4 = U$5(z$2), de = Object.assign(D$4, { features: _$2 });
function Q$3(t = !0) {
	let n = (0, import_react.useRef)(t$5.slice());
	return m$8(([e], [o]) => {
		o === !0 && e === !1 && t$13(() => {
			n.current.splice(0);
		}), o === !1 && e === !0 && (n.current = t$5.slice());
	}, [
		t,
		t$5,
		n
	]), o$10(() => {
		var e;
		return (e = n.current.find((o) => o != null && o.isConnected)) != null ? e : null;
	});
}
function Y$1({ ownerDocument: t }, n) {
	let e = Q$3(n);
	m$8(() => {
		n || (t == null ? void 0 : t.activeElement) === (t == null ? void 0 : t.body) && y$5(e());
	}, [n]), c$8(() => {
		n && y$5(e());
	});
}
function Z$4({ ownerDocument: t, container: n, initialFocus: e }, o) {
	let l = (0, import_react.useRef)(null), c = f$6();
	return m$8(() => {
		if (!o) return;
		let r = n.current;
		r && t$13(() => {
			if (!c.current) return;
			let s = t == null ? void 0 : t.activeElement;
			if (e != null && e.current) {
				if ((e == null ? void 0 : e.current) === s) {
					l.current = s;
					return;
				}
			} else if (r.contains(s)) {
				l.current = s;
				return;
			}
			e != null && e.current ? y$5(e.current) : O$2(r, M$5.First) === N$5.Error && console.warn("There are no focusable elements inside the <FocusTrap />"), l.current = t == null ? void 0 : t.activeElement;
		});
	}, [o]), l;
}
function $$4({ ownerDocument: t, container: n, containers: e, previousActiveElement: o }, l) {
	let c = f$6();
	E$4(t == null ? void 0 : t.defaultView, "focus", (r) => {
		if (!l || !c.current) return;
		let s = P$2(e);
		n.current instanceof HTMLElement && s.add(n.current);
		let i = o.current;
		if (!i) return;
		let u = r.target;
		u && u instanceof HTMLElement ? S$6(s, u) ? (o.current = u, y$5(u)) : (r.preventDefault(), r.stopPropagation(), y$5(i)) : y$5(o.current);
	}, !0);
}
function S$6(t, n) {
	for (let e of t) if (e.contains(n)) return !0;
	return !1;
}
//#endregion
//#region node_modules/@headlessui/react/dist/internal/portal-force-root.js
var e = (0, import_react.createContext)(!1);
function a$7() {
	return (0, import_react.useContext)(e);
}
function l$5(o) {
	return import_react.createElement(e.Provider, { value: o.force }, o.children);
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/portal/portal.js
function F$5(p) {
	let n = a$7(), l = (0, import_react.useContext)(_$1), e = n$4(p), [a, o] = (0, import_react.useState)(() => {
		if (!n && l !== null || s$14.isServer) return null;
		let t = e == null ? void 0 : e.getElementById("headlessui-portal-root");
		if (t) return t;
		if (e === null) return null;
		let r = e.createElement("div");
		return r.setAttribute("id", "headlessui-portal-root"), e.body.appendChild(r);
	});
	return (0, import_react.useEffect)(() => {
		a !== null && (e != null && e.body.contains(a) || e == null || e.body.appendChild(a));
	}, [a, e]), (0, import_react.useEffect)(() => {
		n || l !== null && o(l.current);
	}, [
		l,
		o,
		n
	]), a;
}
var U$3 = import_react.Fragment;
function N$3(p, n) {
	let l = p, e = (0, import_react.useRef)(null), a = y$3(T$2((u) => {
		e.current = u;
	}), n), o = n$4(e), t = F$5(e), [r] = (0, import_react.useState)(() => {
		var u;
		return s$14.isServer ? null : (u = o == null ? void 0 : o.createElement("div")) != null ? u : null;
	}), i = (0, import_react.useContext)(f$5), v = l$9();
	return l$10(() => {
		!t || !r || t.contains(r) || (r.setAttribute("data-headlessui-portal", ""), t.appendChild(r));
	}, [t, r]), l$10(() => {
		if (r && i) return i.register(r);
	}, [i, r]), c$8(() => {
		var u;
		!t || !r || (r instanceof Node && t.contains(r) && t.removeChild(r), t.childNodes.length <= 0 && ((u = t.parentElement) == null || u.removeChild(t)));
	}), v ? !t || !r ? null : (0, import_react_dom.createPortal)(C$5({
		ourProps: { ref: a },
		theirProps: l,
		defaultTag: U$3,
		name: "Portal"
	}), r) : null;
}
var S$5 = import_react.Fragment, _$1 = (0, import_react.createContext)(null);
function j$1(p, n) {
	let { target: l, ...e } = p, o = { ref: y$3(n) };
	return import_react.createElement(_$1.Provider, { value: l }, C$5({
		ourProps: o,
		theirProps: e,
		defaultTag: S$5,
		name: "Popover.Group"
	}));
}
var f$5 = (0, import_react.createContext)(null);
function ee$5() {
	let p = (0, import_react.useContext)(f$5), n = (0, import_react.useRef)([]), l = o$10((o) => (n.current.push(o), p && p.register(o), () => e(o))), e = o$10((o) => {
		let t = n.current.indexOf(o);
		t !== -1 && n.current.splice(t, 1), p && p.unregister(o);
	}), a = (0, import_react.useMemo)(() => ({
		register: l,
		unregister: e,
		portals: n
	}), [
		l,
		e,
		n
	]);
	return [n, (0, import_react.useMemo)(() => function({ children: t }) {
		return import_react.createElement(f$5.Provider, { value: a }, t);
	}, [a])];
}
var D$3 = U$5(N$3), I$6 = U$5(j$1), te = Object.assign(D$3, { Group: I$6 });
//#endregion
//#region node_modules/@headlessui/react/dist/use-sync-external-store-shim/useSyncExternalStoreShimClient.js
function i(e, t) {
	return e === t && (e !== 0 || 1 / e === 1 / t) || e !== e && t !== t;
}
var d$6 = typeof Object.is == "function" ? Object.is : i, { useState: u$4, useEffect: h$5, useLayoutEffect: f$4, useDebugValue: p$1 } = import_react;
function y$2(e, t, c) {
	const a = t(), [{ inst: n }, o] = u$4({ inst: {
		value: a,
		getSnapshot: t
	} });
	return f$4(() => {
		n.value = a, n.getSnapshot = t, r$1(n) && o({ inst: n });
	}, [
		e,
		a,
		t
	]), h$5(() => (r$1(n) && o({ inst: n }), e(() => {
		r$1(n) && o({ inst: n });
	})), [e]), p$1(a), a;
}
function r$1(e) {
	const t = e.getSnapshot, c = e.value;
	try {
		return !d$6(c, t());
	} catch {
		return !0;
	}
}
//#endregion
//#region node_modules/@headlessui/react/dist/use-sync-external-store-shim/useSyncExternalStoreShimServer.js
function t$2(r, e, n) {
	return e();
}
//#endregion
//#region node_modules/@headlessui/react/dist/use-sync-external-store-shim/index.js
var c$6 = !(typeof window != "undefined" && typeof window.document != "undefined" && typeof window.document.createElement != "undefined") ? t$2 : y$2, a$6 = "useSyncExternalStore" in import_react ? ((n) => n.useSyncExternalStore)(import_react) : c$6;
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-store.js
function S$4(t) {
	return a$6(t.subscribe, t.getSnapshot, t.getSnapshot);
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/store.js
function a$5(o, r) {
	let t = o(), n = /* @__PURE__ */ new Set();
	return {
		getSnapshot() {
			return t;
		},
		subscribe(e) {
			return n.add(e), () => n.delete(e);
		},
		dispatch(e, ...s) {
			let i = r[e].call(t, ...s);
			i && (t = i, n.forEach((c) => c()));
		}
	};
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/document-overflow/adjust-scrollbar-padding.js
function c$5() {
	let o;
	return {
		before({ doc: e }) {
			var l;
			let n = e.documentElement;
			o = ((l = e.defaultView) != null ? l : window).innerWidth - n.clientWidth;
		},
		after({ doc: e, d: n }) {
			let t = e.documentElement, l = t.clientWidth - t.offsetWidth, r = o - l;
			n.style(t, "paddingRight", `${r}px`);
		}
	};
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/document-overflow/handle-ios-locking.js
function d$5() {
	return t$11() ? { before({ doc: r, d: l, meta: c }) {
		function o(a) {
			return c.containers.flatMap((n) => n()).some((n) => n.contains(a));
		}
		l.microTask(() => {
			var s;
			if (window.getComputedStyle(r.documentElement).scrollBehavior !== "auto") {
				let t = o$8();
				t.style(r.documentElement, "scrollBehavior", "auto"), l.add(() => l.microTask(() => t.dispose()));
			}
			let a = (s = window.scrollY) != null ? s : window.pageYOffset, n = null;
			l.addEventListener(r, "click", (t) => {
				if (t.target instanceof HTMLElement) try {
					let e = t.target.closest("a");
					if (!e) return;
					let { hash: f } = new URL(e.href), i = r.querySelector(f);
					i && !o(i) && (n = i);
				} catch {}
			}, !0), l.addEventListener(r, "touchstart", (t) => {
				if (t.target instanceof HTMLElement) if (o(t.target)) {
					let e = t.target;
					for (; e.parentElement && o(e.parentElement);) e = e.parentElement;
					l.style(e, "overscrollBehavior", "contain");
				} else l.style(t.target, "touchAction", "none");
			}), l.addEventListener(r, "touchmove", (t) => {
				if (t.target instanceof HTMLElement) if (o(t.target)) {
					let e = t.target;
					for (; e.parentElement && e.dataset.headlessuiPortal !== "" && !(e.scrollHeight > e.clientHeight || e.scrollWidth > e.clientWidth);) e = e.parentElement;
					e.dataset.headlessuiPortal === "" && t.preventDefault();
				} else t.preventDefault();
			}, { passive: !1 }), l.add(() => {
				var e;
				a !== ((e = window.scrollY) != null ? e : window.pageYOffset) && window.scrollTo(0, a), n && n.isConnected && (n.scrollIntoView({ block: "nearest" }), n = null);
			});
		});
	} } : {};
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/document-overflow/prevent-scroll.js
function l$4() {
	return { before({ doc: e, d: o }) {
		o.style(e.documentElement, "overflow", "hidden");
	} };
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/document-overflow/overflow-store.js
function m$5(e) {
	let n = {};
	for (let t of e) Object.assign(n, t(n));
	return n;
}
var a$4 = a$5(() => /* @__PURE__ */ new Map(), {
	PUSH(e, n) {
		var o;
		let t = (o = this.get(e)) != null ? o : {
			doc: e,
			count: 0,
			d: o$8(),
			meta: /* @__PURE__ */ new Set()
		};
		return t.count++, t.meta.add(n), this.set(e, t), this;
	},
	POP(e, n) {
		let t = this.get(e);
		return t && (t.count--, t.meta.delete(n)), this;
	},
	SCROLL_PREVENT({ doc: e, d: n, meta: t }) {
		let o = {
			doc: e,
			d: n,
			meta: m$5(t)
		}, c = [
			d$5(),
			c$5(),
			l$4()
		];
		c.forEach(({ before: r }) => r == null ? void 0 : r(o)), c.forEach(({ after: r }) => r == null ? void 0 : r(o));
	},
	SCROLL_ALLOW({ d: e }) {
		e.dispose();
	},
	TEARDOWN({ doc: e }) {
		this.delete(e);
	}
});
a$4.subscribe(() => {
	let e = a$4.getSnapshot(), n = /* @__PURE__ */ new Map();
	for (let [t] of e) n.set(t, t.documentElement.style.overflow);
	for (let t of e.values()) {
		let o = n.get(t.doc) === "hidden", c = t.count !== 0;
		(c && !o || !c && o) && a$4.dispatch(t.count > 0 ? "SCROLL_PREVENT" : "SCROLL_ALLOW", t), t.count === 0 && a$4.dispatch("TEARDOWN", t);
	}
});
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/document-overflow/use-document-overflow.js
function p(e, r, n) {
	let f = S$4(a$4), o = e ? f.get(e) : void 0, i = o ? o.count > 0 : !1;
	return l$10(() => {
		if (!(!e || !r)) return a$4.dispatch("PUSH", e, n), () => a$4.dispatch("POP", e, n);
	}, [r, e]), i;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-inert.js
var u$3 = /* @__PURE__ */ new Map(), t$1 = /* @__PURE__ */ new Map();
function b$5(r, l = !0) {
	l$10(() => {
		var o;
		if (!l) return;
		let e = typeof r == "function" ? r() : r.current;
		if (!e) return;
		function a() {
			var d;
			if (!e) return;
			let i = (d = t$1.get(e)) != null ? d : 1;
			if (i === 1 ? t$1.delete(e) : t$1.set(e, i - 1), i !== 1) return;
			let n = u$3.get(e);
			n && (n["aria-hidden"] === null ? e.removeAttribute("aria-hidden") : e.setAttribute("aria-hidden", n["aria-hidden"]), e.inert = n.inert, u$3.delete(e));
		}
		let f = (o = t$1.get(e)) != null ? o : 0;
		return t$1.set(e, f + 1), f !== 0 || (u$3.set(e, {
			"aria-hidden": e.getAttribute("aria-hidden"),
			inert: e.inert
		}), e.setAttribute("aria-hidden", "true"), e.inert = !0), a;
	}, [r, l]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-root-containers.js
function N$2({ defaultContainers: o = [], portals: r, mainTreeNodeRef: u } = {}) {
	var f;
	let t = (0, import_react.useRef)((f = u == null ? void 0 : u.current) != null ? f : null), l = n$4(t), c = o$10(() => {
		var i, s, a;
		let n = [];
		for (let e of o) e !== null && (e instanceof HTMLElement ? n.push(e) : "current" in e && e.current instanceof HTMLElement && n.push(e.current));
		if (r != null && r.current) for (let e of r.current) n.push(e);
		for (let e of (i = l == null ? void 0 : l.querySelectorAll("html > *, body > *")) != null ? i : []) e !== document.body && e !== document.head && e instanceof HTMLElement && e.id !== "headlessui-portal-root" && (e.contains(t.current) || e.contains((a = (s = t.current) == null ? void 0 : s.getRootNode()) == null ? void 0 : a.host) || n.some((L) => e.contains(L)) || n.push(e));
		return n;
	});
	return {
		resolveContainers: c,
		contains: o$10((n) => c().some((i) => i.contains(n))),
		mainTreeNodeRef: t,
		MainTreeNode: (0, import_react.useMemo)(() => function() {
			return u != null ? null : import_react.createElement(u$8, {
				features: s$7.Hidden,
				ref: t
			});
		}, [t, u])
	};
}
function y$1() {
	let o = (0, import_react.useRef)(null);
	return {
		mainTreeNodeRef: o,
		MainTreeNode: (0, import_react.useMemo)(() => function() {
			return import_react.createElement(u$8, {
				features: s$7.Hidden,
				ref: o
			});
		}, [o])
	};
}
//#endregion
//#region node_modules/@headlessui/react/dist/internal/stack-context.js
var a$3 = (0, import_react.createContext)(() => {});
a$3.displayName = "StackContext";
var s$3 = ((e) => (e[e.Add = 0] = "Add", e[e.Remove = 1] = "Remove", e))(s$3 || {});
function x$1() {
	return (0, import_react.useContext)(a$3);
}
function b$4({ children: i, onUpdate: r, type: e, element: n, enabled: u }) {
	let l = x$1(), o = o$10((...t) => {
		r?.(...t), l(...t);
	});
	return l$10(() => {
		let t = u === void 0 || u === !0;
		return t && o(0, e, n), () => {
			t && o(1, e, n);
		};
	}, [
		o,
		e,
		n,
		u
	]), import_react.createElement(a$3.Provider, { value: o }, i);
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/description/description.js
var d$2 = (0, import_react.createContext)(null);
function f$3() {
	let r = (0, import_react.useContext)(d$2);
	if (r === null) {
		let t = /* @__PURE__ */ new Error("You used a <Description /> component, but it is not inside a relevant parent.");
		throw Error.captureStackTrace && Error.captureStackTrace(t, f$3), t;
	}
	return r;
}
function w$2() {
	let [r, t] = (0, import_react.useState)([]);
	return [r.length > 0 ? r.join(" ") : void 0, (0, import_react.useMemo)(() => function(e) {
		let i = o$10((s) => (t((o) => [...o, s]), () => t((o) => {
			let p = o.slice(), c = p.indexOf(s);
			return c !== -1 && p.splice(c, 1), p;
		}))), n = (0, import_react.useMemo)(() => ({
			register: i,
			slot: e.slot,
			name: e.name,
			props: e.props
		}), [
			i,
			e.slot,
			e.name,
			e.props
		]);
		return import_react.createElement(d$2.Provider, { value: n }, e.children);
	}, [t])];
}
var I$5 = "p";
function S$3(r, t) {
	let a = I$9(), { id: e = `headlessui-description-${a}`, ...i } = r, n = f$3(), s = y$3(t);
	l$10(() => n.register(e), [e, n.register]);
	return C$5({
		ourProps: {
			ref: s,
			...n.props,
			id: e
		},
		theirProps: i,
		slot: n.slot || {},
		defaultTag: I$5,
		name: n.name || "Description"
	});
}
var h$4 = U$5(S$3), G$2 = Object.assign(h$4, {});
//#endregion
//#region node_modules/@headlessui/react/dist/components/dialog/dialog.js
var Me$1 = ((r) => (r[r.Open = 0] = "Open", r[r.Closed = 1] = "Closed", r))(Me$1 || {}), we$2 = ((e) => (e[e.SetTitleId = 0] = "SetTitleId", e))(we$2 || {});
var He$3 = { [0](o, e) {
	return o.titleId === e.id ? o : {
		...o,
		titleId: e.id
	};
} }, I$4 = (0, import_react.createContext)(null);
I$4.displayName = "DialogContext";
function b$3(o) {
	let e = (0, import_react.useContext)(I$4);
	if (e === null) {
		let r = /* @__PURE__ */ new Error(`<${o} /> is missing a parent <Dialog /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(r, b$3), r;
	}
	return e;
}
function Be$1(o, e, r = () => [document.body]) {
	p(o, e, (i) => {
		var n;
		return { containers: [...(n = i.containers) != null ? n : [], r] };
	});
}
function Ge$3(o, e) {
	return u$11(e.type, He$3, o, e);
}
var Ne$3 = "div", Ue$1 = O$1.RenderStrategy | O$1.Static;
function We$2(o, e) {
	let r = I$9(), { id: i = `headlessui-dialog-${r}`, open: n, onClose: l, initialFocus: s, role: a = "dialog", __demoMode: T = !1, ...m } = o, [M, f] = (0, import_react.useState)(0), U = (0, import_react.useRef)(!1);
	a = function() {
		return a === "dialog" || a === "alertdialog" ? a : (U.current || (U.current = !0, console.warn(`Invalid role [${a}] passed to <Dialog />. Only \`dialog\` and and \`alertdialog\` are supported. Using \`dialog\` instead.`)), "dialog");
	}();
	let E = u$7();
	n === void 0 && E !== null && (n = (E & d$10.Open) === d$10.Open);
	let D = (0, import_react.useRef)(null), ee = y$3(D, e), g = n$4(D), W = o.hasOwnProperty("open") || E !== null, $ = o.hasOwnProperty("onClose");
	if (!W && !$) throw new Error("You have to provide an `open` and an `onClose` prop to the `Dialog` component.");
	if (!W) throw new Error("You provided an `onClose` prop to the `Dialog`, but forgot an `open` prop.");
	if (!$) throw new Error("You provided an `open` prop to the `Dialog`, but forgot an `onClose` prop.");
	if (typeof n != "boolean") throw new Error(`You provided an \`open\` prop to the \`Dialog\`, but the value is not a boolean. Received: ${n}`);
	if (typeof l != "function") throw new Error(`You provided an \`onClose\` prop to the \`Dialog\`, but the value is not a function. Received: ${l}`);
	let p = n ? 0 : 1, [h, te$4] = (0, import_react.useReducer)(Ge$3, {
		titleId: null,
		descriptionId: null,
		panelRef: (0, import_react.createRef)()
	}), P = o$10(() => l(!1)), Y = o$10((t) => te$4({
		type: 0,
		id: t
	})), S = l$9() ? T ? !1 : p === 0 : !1, x = M > 1, j = (0, import_react.useContext)(I$4) !== null, [oe, re] = ee$5(), { resolveContainers: w, mainTreeNodeRef: L, MainTreeNode: le } = N$2({
		portals: oe,
		defaultContainers: [{ get current() {
			var t;
			return (t = h.panelRef.current) != null ? t : D.current;
		} }]
	}), ae = x ? "parent" : "leaf", J = E !== null ? (E & d$10.Closing) === d$10.Closing : !1, ie = (() => j || J ? !1 : S)();
	b$5((0, import_react.useCallback)(() => {
		var t, c;
		return (c = Array.from((t = g == null ? void 0 : g.querySelectorAll("body > *")) != null ? t : []).find((d) => d.id === "headlessui-portal-root" ? !1 : d.contains(L.current) && d instanceof HTMLElement)) != null ? c : null;
	}, [L]), ie);
	let pe = (() => x ? !0 : S)();
	b$5((0, import_react.useCallback)(() => {
		var t, c;
		return (c = Array.from((t = g == null ? void 0 : g.querySelectorAll("[data-headlessui-portal]")) != null ? t : []).find((d) => d.contains(L.current) && d instanceof HTMLElement)) != null ? c : null;
	}, [L]), pe);
	y$4(w, (t) => {
		t.preventDefault(), P();
	}, (() => !(!S || x))());
	let fe = (() => !(x || p !== 0))();
	E$4(g == null ? void 0 : g.defaultView, "keydown", (t) => {
		fe && (t.defaultPrevented || t.key === o$1.Escape && (t.preventDefault(), t.stopPropagation(), P()));
	});
	Be$1(g, (() => !(J || p !== 0 || j))(), w), (0, import_react.useEffect)(() => {
		if (p !== 0 || !D.current) return;
		let t = new ResizeObserver((c) => {
			for (let d of c) {
				let F = d.target.getBoundingClientRect();
				F.x === 0 && F.y === 0 && F.width === 0 && F.height === 0 && P();
			}
		});
		return t.observe(D.current), () => t.disconnect();
	}, [
		p,
		D,
		P
	]);
	let [Te, ce] = w$2(), De = (0, import_react.useMemo)(() => [{
		dialogState: p,
		close: P,
		setTitleId: Y
	}, h], [
		p,
		h,
		P,
		Y
	]), X = (0, import_react.useMemo)(() => ({ open: p === 0 }), [p]), me = {
		ref: ee,
		id: i,
		role: a,
		"aria-modal": p === 0 ? !0 : void 0,
		"aria-labelledby": h.titleId,
		"aria-describedby": Te
	};
	return import_react.createElement(b$4, {
		type: "Dialog",
		enabled: p === 0,
		element: D,
		onUpdate: o$10((t, c) => {
			c === "Dialog" && u$11(t, {
				[s$3.Add]: () => f((d) => d + 1),
				[s$3.Remove]: () => f((d) => d - 1)
			});
		})
	}, import_react.createElement(l$5, { force: !0 }, import_react.createElement(te, null, import_react.createElement(I$4.Provider, { value: De }, import_react.createElement(te.Group, { target: D }, import_react.createElement(l$5, { force: !1 }, import_react.createElement(ce, {
		slot: X,
		name: "Dialog.Description"
	}, import_react.createElement(de, {
		initialFocus: s,
		containers: w,
		features: S ? u$11(ae, {
			parent: de.features.RestoreFocus,
			leaf: de.features.All & ~de.features.FocusLock
		}) : de.features.None
	}, import_react.createElement(re, null, C$5({
		ourProps: me,
		theirProps: m,
		slot: X,
		defaultTag: Ne$3,
		features: Ue$1,
		visible: p === 0,
		name: "Dialog"
	}))))))))), import_react.createElement(le, null));
}
var $e$3 = "div";
function Ye$2(o, e) {
	let r = I$9(), { id: i = `headlessui-dialog-overlay-${r}`, ...n } = o, [{ dialogState: l, close: s }] = b$3("Dialog.Overlay"), a = y$3(e), T = o$10((f) => {
		if (f.target === f.currentTarget) {
			if (r$4(f.currentTarget)) return f.preventDefault();
			f.preventDefault(), f.stopPropagation(), s();
		}
	}), m = (0, import_react.useMemo)(() => ({ open: l === 0 }), [l]);
	return C$5({
		ourProps: {
			ref: a,
			id: i,
			"aria-hidden": !0,
			onClick: T
		},
		theirProps: n,
		slot: m,
		defaultTag: $e$3,
		name: "Dialog.Overlay"
	});
}
var je$2 = "div";
function Je$2(o, e) {
	let r = I$9(), { id: i = `headlessui-dialog-backdrop-${r}`, ...n } = o, [{ dialogState: l }, s] = b$3("Dialog.Backdrop"), a = y$3(e);
	(0, import_react.useEffect)(() => {
		if (s.panelRef.current === null) throw new Error("A <Dialog.Backdrop /> component is being used, but a <Dialog.Panel /> component is missing.");
	}, [s.panelRef]);
	let T = (0, import_react.useMemo)(() => ({ open: l === 0 }), [l]);
	return import_react.createElement(l$5, { force: !0 }, import_react.createElement(te, null, C$5({
		ourProps: {
			ref: a,
			id: i,
			"aria-hidden": !0
		},
		theirProps: n,
		slot: T,
		defaultTag: je$2,
		name: "Dialog.Backdrop"
	})));
}
var Xe$2 = "div";
function Ke$2(o, e) {
	let r = I$9(), { id: i = `headlessui-dialog-panel-${r}`, ...n } = o, [{ dialogState: l }, s] = b$3("Dialog.Panel"), a = y$3(e, s.panelRef), T = (0, import_react.useMemo)(() => ({ open: l === 0 }), [l]);
	return C$5({
		ourProps: {
			ref: a,
			id: i,
			onClick: o$10((f) => {
				f.stopPropagation();
			})
		},
		theirProps: n,
		slot: T,
		defaultTag: Xe$2,
		name: "Dialog.Panel"
	});
}
var Ve$2 = "h2";
function qe$4(o, e) {
	let r = I$9(), { id: i = `headlessui-dialog-title-${r}`, ...n } = o, [{ dialogState: l, setTitleId: s }] = b$3("Dialog.Title"), a = y$3(e);
	(0, import_react.useEffect)(() => (s(i), () => s(null)), [i, s]);
	let T = (0, import_react.useMemo)(() => ({ open: l === 0 }), [l]);
	return C$5({
		ourProps: {
			ref: a,
			id: i
		},
		theirProps: n,
		slot: T,
		defaultTag: Ve$2,
		name: "Dialog.Title"
	});
}
var ze$2 = U$5(We$2), Qe$2 = U$5(Je$2), Ze$2 = U$5(Ke$2), et$2 = U$5(Ye$2), tt$2 = U$5(qe$4), _t = Object.assign(ze$2, {
	Backdrop: Qe$2,
	Panel: Ze$2,
	Overlay: et$2,
	Title: tt$2,
	Description: G$2
});
//#endregion
//#region node_modules/@headlessui/react/dist/utils/start-transition.js
var t;
var a$2 = (t = import_react.startTransition) != null ? t : function(i) {
	i();
};
//#endregion
//#region node_modules/@headlessui/react/dist/components/disclosure/disclosure.js
var Q$2 = ((o) => (o[o.Open = 0] = "Open", o[o.Closed = 1] = "Closed", o))(Q$2 || {}), V$2 = ((t) => (t[t.ToggleDisclosure = 0] = "ToggleDisclosure", t[t.CloseDisclosure = 1] = "CloseDisclosure", t[t.SetButtonId = 2] = "SetButtonId", t[t.SetPanelId = 3] = "SetPanelId", t[t.LinkPanel = 4] = "LinkPanel", t[t.UnlinkPanel = 5] = "UnlinkPanel", t))(V$2 || {});
var Y = {
	[0]: (e) => ({
		...e,
		disclosureState: u$11(e.disclosureState, {
			[0]: 1,
			[1]: 0
		})
	}),
	[1]: (e) => e.disclosureState === 1 ? e : {
		...e,
		disclosureState: 1
	},
	[4](e) {
		return e.linkedPanel === !0 ? e : {
			...e,
			linkedPanel: !0
		};
	},
	[5](e) {
		return e.linkedPanel === !1 ? e : {
			...e,
			linkedPanel: !1
		};
	},
	[2](e, n) {
		return e.buttonId === n.buttonId ? e : {
			...e,
			buttonId: n.buttonId
		};
	},
	[3](e, n) {
		return e.panelId === n.panelId ? e : {
			...e,
			panelId: n.panelId
		};
	}
}, M$3 = (0, import_react.createContext)(null);
M$3.displayName = "DisclosureContext";
function _(e) {
	let n = (0, import_react.useContext)(M$3);
	if (n === null) {
		let o = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Disclosure /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(o, _), o;
	}
	return n;
}
var v$3 = (0, import_react.createContext)(null);
v$3.displayName = "DisclosureAPIContext";
function K$1(e) {
	let n = (0, import_react.useContext)(v$3);
	if (n === null) {
		let o = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Disclosure /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(o, K$1), o;
	}
	return n;
}
var F$4 = (0, import_react.createContext)(null);
F$4.displayName = "DisclosurePanelContext";
function Z$3() {
	return (0, import_react.useContext)(F$4);
}
function ee$4(e, n) {
	return u$11(n.type, Y, e, n);
}
var te$3 = import_react.Fragment;
function ne$3(e, n) {
	let { defaultOpen: o = !1, ...i } = e, f = (0, import_react.useRef)(null), l = y$3(n, T$2((u) => {
		f.current = u;
	}, e.as === void 0 || e.as === import_react.Fragment)), t = (0, import_react.useRef)(null), d = (0, import_react.useRef)(null), s = (0, import_react.useReducer)(ee$4, {
		disclosureState: o ? 0 : 1,
		linkedPanel: !1,
		buttonRef: d,
		panelRef: t,
		buttonId: null,
		panelId: null
	}), [{ disclosureState: c, buttonId: a }, D] = s, p = o$10((u) => {
		D({ type: 1 });
		let y = o$5(f);
		if (!y || !a) return;
		(() => u ? u instanceof HTMLElement ? u : u.current instanceof HTMLElement ? u.current : y.getElementById(a) : y.getElementById(a))()?.focus();
	}), P = (0, import_react.useMemo)(() => ({ close: p }), [p]), T = (0, import_react.useMemo)(() => ({
		open: c === 0,
		close: p
	}), [c, p]), C = { ref: l };
	return import_react.createElement(M$3.Provider, { value: s }, import_react.createElement(v$3.Provider, { value: P }, import_react.createElement(s$6, { value: u$11(c, {
		[0]: d$10.Open,
		[1]: d$10.Closed
	}) }, C$5({
		ourProps: C,
		theirProps: i,
		slot: T,
		defaultTag: te$3,
		name: "Disclosure"
	}))));
}
var le$1 = "button";
function oe$3(e, n) {
	let o = I$9(), { id: i = `headlessui-disclosure-button-${o}`, ...f } = e, [l, t] = _("Disclosure.Button"), d = Z$3(), s = d === null ? !1 : d === l.panelId, c = (0, import_react.useRef)(null), a = y$3(c, n, s ? null : l.buttonRef), D = I$7();
	(0, import_react.useEffect)(() => {
		if (!s) return t({
			type: 2,
			buttonId: i
		}), () => {
			t({
				type: 2,
				buttonId: null
			});
		};
	}, [
		i,
		t,
		s
	]);
	let p = o$10((r) => {
		var m;
		if (s) {
			if (l.disclosureState === 1) return;
			switch (r.key) {
				case o$1.Space:
				case o$1.Enter:
					r.preventDefault(), r.stopPropagation(), t({ type: 0 }), (m = l.buttonRef.current) == null || m.focus();
					break;
			}
		} else switch (r.key) {
			case o$1.Space:
			case o$1.Enter:
				r.preventDefault(), r.stopPropagation(), t({ type: 0 });
				break;
		}
	}), P = o$10((r) => {
		switch (r.key) {
			case o$1.Space:
				r.preventDefault();
				break;
		}
	}), T = o$10((r) => {
		var m;
		r$4(r.currentTarget) || e.disabled || (s ? (t({ type: 0 }), (m = l.buttonRef.current) == null || m.focus()) : t({ type: 0 }));
	}), C = (0, import_react.useMemo)(() => ({ open: l.disclosureState === 0 }), [l]), u = T$3(e, c);
	return C$5({
		mergeRefs: D,
		ourProps: s ? {
			ref: a,
			type: u,
			onKeyDown: p,
			onClick: T
		} : {
			ref: a,
			id: i,
			type: u,
			"aria-expanded": l.disclosureState === 0,
			"aria-controls": l.linkedPanel ? l.panelId : void 0,
			onKeyDown: p,
			onKeyUp: P,
			onClick: T
		},
		theirProps: f,
		slot: C,
		defaultTag: le$1,
		name: "Disclosure.Button"
	});
}
var re$3 = "div", se$2 = O$1.RenderStrategy | O$1.Static;
function ue$4(e, n) {
	let o = I$9(), { id: i = `headlessui-disclosure-panel-${o}`, ...f } = e, [l, t] = _("Disclosure.Panel"), { close: d } = K$1("Disclosure.Panel"), s = I$7(), c = y$3(n, l.panelRef, (T) => {
		a$2(() => t({ type: T ? 4 : 5 }));
	});
	(0, import_react.useEffect)(() => (t({
		type: 3,
		panelId: i
	}), () => {
		t({
			type: 3,
			panelId: null
		});
	}), [i, t]);
	let a = u$7(), D = (() => a !== null ? (a & d$10.Open) === d$10.Open : l.disclosureState === 0)(), p = (0, import_react.useMemo)(() => ({
		open: l.disclosureState === 0,
		close: d
	}), [l, d]), P = {
		ref: c,
		id: i
	};
	return import_react.createElement(F$4.Provider, { value: l.panelId }, C$5({
		mergeRefs: s,
		ourProps: P,
		theirProps: f,
		slot: p,
		defaultTag: re$3,
		features: se$2,
		visible: D,
		name: "Disclosure.Panel"
	}));
}
var ie$1 = U$5(ne$3), ae$1 = U$5(oe$3), pe = U$5(ue$4), Ae = Object.assign(ie$1, {
	Button: ae$1,
	Panel: pe
});
//#endregion
//#region node_modules/@headlessui/react/dist/utils/get-text-value.js
var a$1 = /([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g;
function o(e) {
	var r, i;
	let n = (r = e.innerText) != null ? r : "", t = e.cloneNode(!0);
	if (!(t instanceof HTMLElement)) return n;
	let u = !1;
	for (let f of t.querySelectorAll("[hidden],[aria-hidden],[role=\"img\"]")) f.remove(), u = !0;
	let l = u ? (i = t.innerText) != null ? i : "" : n;
	return a$1.test(l) && (l = l.replace(a$1, "")), l;
}
function g$1(e) {
	let n = e.getAttribute("aria-label");
	if (typeof n == "string") return n.trim();
	let t = e.getAttribute("aria-labelledby");
	if (t) {
		let u = t.split(" ").map((l) => {
			let r = document.getElementById(l);
			if (r) {
				let i = r.getAttribute("aria-label");
				return typeof i == "string" ? i.trim() : o(r).trim();
			}
			return null;
		}).filter(Boolean);
		if (u.length > 0) return u.join(", ");
	}
	return o(e).trim();
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-text-value.js
function s$2(c) {
	let t = (0, import_react.useRef)(""), r = (0, import_react.useRef)("");
	return o$10(() => {
		let e = c.current;
		if (!e) return "";
		let u = e.innerText;
		if (t.current === u) return r.current;
		let n = g$1(e).trim().toLowerCase();
		return t.current = u, r.current = n, n;
	});
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/listbox/listbox.js
var Be = ((n) => (n[n.Open = 0] = "Open", n[n.Closed = 1] = "Closed", n))(Be || {}), He$2 = ((n) => (n[n.Single = 0] = "Single", n[n.Multi = 1] = "Multi", n))(He$2 || {}), Ge$2 = ((n) => (n[n.Pointer = 0] = "Pointer", n[n.Other = 1] = "Other", n))(Ge$2 || {}), Ne$2 = ((i) => (i[i.OpenListbox = 0] = "OpenListbox", i[i.CloseListbox = 1] = "CloseListbox", i[i.GoToOption = 2] = "GoToOption", i[i.Search = 3] = "Search", i[i.ClearSearch = 4] = "ClearSearch", i[i.RegisterOption = 5] = "RegisterOption", i[i.UnregisterOption = 6] = "UnregisterOption", i[i.RegisterLabel = 7] = "RegisterLabel", i))(Ne$2 || {});
function z$1(e, a = (n) => n) {
	let n = e.activeOptionIndex !== null ? e.options[e.activeOptionIndex] : null, r = I$8(a(e.options.slice()), (t) => t.dataRef.current.domRef.current), l = n ? r.indexOf(n) : null;
	return l === -1 && (l = null), {
		options: r,
		activeOptionIndex: l
	};
}
var je$1 = {
	[1](e) {
		return e.dataRef.current.disabled || e.listboxState === 1 ? e : {
			...e,
			activeOptionIndex: null,
			listboxState: 1
		};
	},
	[0](e) {
		if (e.dataRef.current.disabled || e.listboxState === 0) return e;
		let a = e.activeOptionIndex, { isSelected: n } = e.dataRef.current, r = e.options.findIndex((l) => n(l.dataRef.current.value));
		return r !== -1 && (a = r), {
			...e,
			listboxState: 0,
			activeOptionIndex: a
		};
	},
	[2](e, a) {
		var l;
		if (e.dataRef.current.disabled || e.listboxState === 1) return e;
		let n = z$1(e), r = f$8(a, {
			resolveItems: () => n.options,
			resolveActiveIndex: () => n.activeOptionIndex,
			resolveId: (t) => t.id,
			resolveDisabled: (t) => t.dataRef.current.disabled
		});
		return {
			...e,
			...n,
			searchQuery: "",
			activeOptionIndex: r,
			activationTrigger: (l = a.trigger) != null ? l : 1
		};
	},
	[3]: (e, a) => {
		if (e.dataRef.current.disabled || e.listboxState === 1) return e;
		let r = e.searchQuery !== "" ? 0 : 1, l = e.searchQuery + a.value.toLowerCase(), p = (e.activeOptionIndex !== null ? e.options.slice(e.activeOptionIndex + r).concat(e.options.slice(0, e.activeOptionIndex + r)) : e.options).find((i) => {
			var b;
			return !i.dataRef.current.disabled && ((b = i.dataRef.current.textValue) == null ? void 0 : b.startsWith(l));
		}), u = p ? e.options.indexOf(p) : -1;
		return u === -1 || u === e.activeOptionIndex ? {
			...e,
			searchQuery: l
		} : {
			...e,
			searchQuery: l,
			activeOptionIndex: u,
			activationTrigger: 1
		};
	},
	[4](e) {
		return e.dataRef.current.disabled || e.listboxState === 1 || e.searchQuery === "" ? e : {
			...e,
			searchQuery: ""
		};
	},
	[5]: (e, a) => {
		let n = {
			id: a.id,
			dataRef: a.dataRef
		}, r = z$1(e, (l) => [...l, n]);
		return e.activeOptionIndex === null && e.dataRef.current.isSelected(a.dataRef.current.value) && (r.activeOptionIndex = r.options.indexOf(n)), {
			...e,
			...r
		};
	},
	[6]: (e, a) => {
		let n = z$1(e, (r) => {
			let l = r.findIndex((t) => t.id === a.id);
			return l !== -1 && r.splice(l, 1), r;
		});
		return {
			...e,
			...n,
			activationTrigger: 1
		};
	},
	[7]: (e, a) => ({
		...e,
		labelId: a.id
	})
}, J$4 = (0, import_react.createContext)(null);
J$4.displayName = "ListboxActionsContext";
function k(e) {
	let a = (0, import_react.useContext)(J$4);
	if (a === null) {
		let n = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Listbox /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(n, k), n;
	}
	return a;
}
var q$3 = (0, import_react.createContext)(null);
q$3.displayName = "ListboxDataContext";
function w$1(e) {
	let a = (0, import_react.useContext)(q$3);
	if (a === null) {
		let n = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Listbox /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(n, w$1), n;
	}
	return a;
}
function Ve$1(e, a) {
	return u$11(a.type, je$1, e, a);
}
var Ke$1 = import_react.Fragment;
function Qe$1(e, a) {
	let { value: n, defaultValue: r, form: l, name: t, onChange: p, by: u = (s, c) => s === c, disabled: i = !1, horizontal: b = !1, multiple: R = !1, ...m } = e;
	const P = b ? "horizontal" : "vertical";
	let S = y$3(a), [g = R ? [] : void 0, x] = T$5(n, p, r), [T, o] = (0, import_react.useReducer)(Ve$1, {
		dataRef: (0, import_react.createRef)(),
		listboxState: 1,
		options: [],
		searchQuery: "",
		labelId: null,
		activeOptionIndex: null,
		activationTrigger: 1
	}), L = (0, import_react.useRef)({
		static: !1,
		hold: !1
	}), U = (0, import_react.useRef)(null), B = (0, import_react.useRef)(null), W = (0, import_react.useRef)(null), I = o$10(typeof u == "string" ? (s, c) => {
		let O = u;
		return (s == null ? void 0 : s[O]) === (c == null ? void 0 : c[O]);
	} : u), A = (0, import_react.useCallback)((s) => u$11(d.mode, {
		[1]: () => g.some((c) => I(c, s)),
		[0]: () => I(g, s)
	}), [g]), d = (0, import_react.useMemo)(() => ({
		...T,
		value: g,
		disabled: i,
		mode: R ? 1 : 0,
		orientation: P,
		compare: I,
		isSelected: A,
		optionsPropsRef: L,
		labelRef: U,
		buttonRef: B,
		optionsRef: W
	}), [
		g,
		i,
		R,
		T
	]);
	l$10(() => {
		T.dataRef.current = d;
	}, [d]), y$4([d.buttonRef, d.optionsRef], (s, c) => {
		var O;
		o({ type: 1 }), h$7(c, T$4.Loose) || (s.preventDefault(), (O = d.buttonRef.current) == null || O.focus());
	}, d.listboxState === 0);
	let H = (0, import_react.useMemo)(() => ({
		open: d.listboxState === 0,
		disabled: i,
		value: g
	}), [
		d,
		i,
		g
	]), ie = o$10((s) => {
		let c = d.options.find((O) => O.id === s);
		c && X(c.dataRef.current.value);
	}), re = o$10(() => {
		if (d.activeOptionIndex !== null) {
			let { dataRef: s, id: c } = d.options[d.activeOptionIndex];
			X(s.current.value), o({
				type: 2,
				focus: c$9.Specific,
				id: c
			});
		}
	}), ae = o$10(() => o({ type: 0 })), le = o$10(() => o({ type: 1 })), se = o$10((s, c, O) => s === c$9.Specific ? o({
		type: 2,
		focus: c$9.Specific,
		id: c,
		trigger: O
	}) : o({
		type: 2,
		focus: s,
		trigger: O
	})), pe = o$10((s, c) => (o({
		type: 5,
		id: s,
		dataRef: c
	}), () => o({
		type: 6,
		id: s
	}))), ue = o$10((s) => (o({
		type: 7,
		id: s
	}), () => o({
		type: 7,
		id: null
	}))), X = o$10((s) => u$11(d.mode, {
		[0]() {
			return x == null ? void 0 : x(s);
		},
		[1]() {
			let c = d.value.slice(), O = c.findIndex((C) => I(C, s));
			return O === -1 ? c.push(s) : c.splice(O, 1), x == null ? void 0 : x(c);
		}
	})), de = o$10((s) => o({
		type: 3,
		value: s
	})), ce = o$10(() => o({ type: 4 })), fe = (0, import_react.useMemo)(() => ({
		onChange: X,
		registerOption: pe,
		registerLabel: ue,
		goToOption: se,
		closeListbox: le,
		openListbox: ae,
		selectActiveOption: re,
		selectOption: ie,
		search: de,
		clearSearch: ce
	}), []), Te = { ref: S }, G = (0, import_react.useRef)(null), be = p$5();
	return (0, import_react.useEffect)(() => {
		G.current && r !== void 0 && be.addEventListener(G.current, "reset", () => {
			x?.(r);
		});
	}, [G, x]), import_react.createElement(J$4.Provider, { value: fe }, import_react.createElement(q$3.Provider, { value: d }, import_react.createElement(s$6, { value: u$11(d.listboxState, {
		[0]: d$10.Open,
		[1]: d$10.Closed
	}) }, t != null && g != null && e$1({ [t]: g }).map(([s, c], O) => import_react.createElement(u$8, {
		features: s$7.Hidden,
		ref: O === 0 ? (C) => {
			var Y;
			G.current = (Y = C == null ? void 0 : C.closest("form")) != null ? Y : null;
		} : void 0,
		...x$2({
			key: s,
			as: "input",
			type: "hidden",
			hidden: !0,
			readOnly: !0,
			form: l,
			disabled: i,
			name: s,
			value: c
		})
	})), C$5({
		ourProps: Te,
		theirProps: m,
		slot: H,
		defaultTag: Ke$1,
		name: "Listbox"
	}))));
}
var We$1 = "button";
function Xe$1(e, a) {
	var x;
	let n = I$9(), { id: r = `headlessui-listbox-button-${n}`, ...l } = e, t = w$1("Listbox.Button"), p = k("Listbox.Button"), u = y$3(t.buttonRef, a), i = p$5(), b = o$10((T) => {
		switch (T.key) {
			case o$1.Space:
			case o$1.Enter:
			case o$1.ArrowDown:
				T.preventDefault(), p.openListbox(), i.nextFrame(() => {
					t.value || p.goToOption(c$9.First);
				});
				break;
			case o$1.ArrowUp:
				T.preventDefault(), p.openListbox(), i.nextFrame(() => {
					t.value || p.goToOption(c$9.Last);
				});
				break;
		}
	}), R = o$10((T) => {
		switch (T.key) {
			case o$1.Space:
				T.preventDefault();
				break;
		}
	}), m = o$10((T) => {
		if (r$4(T.currentTarget)) return T.preventDefault();
		t.listboxState === 0 ? (p.closeListbox(), i.nextFrame(() => {
			var o;
			return (o = t.buttonRef.current) == null ? void 0 : o.focus({ preventScroll: !0 });
		})) : (T.preventDefault(), p.openListbox());
	}), P = i$5(() => {
		if (t.labelId) return [t.labelId, r].join(" ");
	}, [t.labelId, r]), S = (0, import_react.useMemo)(() => ({
		open: t.listboxState === 0,
		disabled: t.disabled,
		value: t.value
	}), [t]);
	return C$5({
		ourProps: {
			ref: u,
			id: r,
			type: T$3(e, t.buttonRef),
			"aria-haspopup": "listbox",
			"aria-controls": (x = t.optionsRef.current) == null ? void 0 : x.id,
			"aria-expanded": t.listboxState === 0,
			"aria-labelledby": P,
			disabled: t.disabled,
			onKeyDown: b,
			onKeyUp: R,
			onClick: m
		},
		theirProps: l,
		slot: S,
		defaultTag: We$1,
		name: "Listbox.Button"
	});
}
var $e$2 = "label";
function ze$1(e, a) {
	let n = I$9(), { id: r = `headlessui-listbox-label-${n}`, ...l } = e, t = w$1("Listbox.Label"), p = k("Listbox.Label"), u = y$3(t.labelRef, a);
	l$10(() => p.registerLabel(r), [r]);
	let i = o$10(() => {
		var m;
		return (m = t.buttonRef.current) == null ? void 0 : m.focus({ preventScroll: !0 });
	}), b = (0, import_react.useMemo)(() => ({
		open: t.listboxState === 0,
		disabled: t.disabled
	}), [t]);
	return C$5({
		ourProps: {
			ref: u,
			id: r,
			onClick: i
		},
		theirProps: l,
		slot: b,
		defaultTag: $e$2,
		name: "Listbox.Label"
	});
}
var Je$1 = "ul", qe$3 = O$1.RenderStrategy | O$1.Static;
function Ye$1(e, a) {
	var T;
	let n = I$9(), { id: r = `headlessui-listbox-options-${n}`, ...l } = e, t = w$1("Listbox.Options"), p = k("Listbox.Options"), u = y$3(t.optionsRef, a), i = p$5(), b = p$5(), R = u$7(), m = (() => R !== null ? (R & d$10.Open) === d$10.Open : t.listboxState === 0)();
	(0, import_react.useEffect)(() => {
		var L;
		let o = t.optionsRef.current;
		o && t.listboxState === 0 && o !== ((L = o$5(o)) == null ? void 0 : L.activeElement) && o.focus({ preventScroll: !0 });
	}, [t.listboxState, t.optionsRef]);
	let P = o$10((o) => {
		switch (b.dispose(), o.key) {
			case o$1.Space: if (t.searchQuery !== "") return o.preventDefault(), o.stopPropagation(), p.search(o.key);
			case o$1.Enter:
				if (o.preventDefault(), o.stopPropagation(), t.activeOptionIndex !== null) {
					let { dataRef: L } = t.options[t.activeOptionIndex];
					p.onChange(L.current.value);
				}
				t.mode === 0 && (p.closeListbox(), o$8().nextFrame(() => {
					var L;
					return (L = t.buttonRef.current) == null ? void 0 : L.focus({ preventScroll: !0 });
				}));
				break;
			case u$11(t.orientation, {
				vertical: o$1.ArrowDown,
				horizontal: o$1.ArrowRight
			}): return o.preventDefault(), o.stopPropagation(), p.goToOption(c$9.Next);
			case u$11(t.orientation, {
				vertical: o$1.ArrowUp,
				horizontal: o$1.ArrowLeft
			}): return o.preventDefault(), o.stopPropagation(), p.goToOption(c$9.Previous);
			case o$1.Home:
			case o$1.PageUp: return o.preventDefault(), o.stopPropagation(), p.goToOption(c$9.First);
			case o$1.End:
			case o$1.PageDown: return o.preventDefault(), o.stopPropagation(), p.goToOption(c$9.Last);
			case o$1.Escape: return o.preventDefault(), o.stopPropagation(), p.closeListbox(), i.nextFrame(() => {
				var L;
				return (L = t.buttonRef.current) == null ? void 0 : L.focus({ preventScroll: !0 });
			});
			case o$1.Tab:
				o.preventDefault(), o.stopPropagation();
				break;
			default:
				o.key.length === 1 && (p.search(o.key), b.setTimeout(() => p.clearSearch(), 350));
				break;
		}
	}), S = i$5(() => {
		var o;
		return (o = t.buttonRef.current) == null ? void 0 : o.id;
	}, [t.buttonRef.current]), g = (0, import_react.useMemo)(() => ({ open: t.listboxState === 0 }), [t]);
	return C$5({
		ourProps: {
			"aria-activedescendant": t.activeOptionIndex === null || (T = t.options[t.activeOptionIndex]) == null ? void 0 : T.id,
			"aria-multiselectable": t.mode === 1 ? !0 : void 0,
			"aria-labelledby": S,
			"aria-orientation": t.orientation,
			id: r,
			onKeyDown: P,
			role: "listbox",
			tabIndex: 0,
			ref: u
		},
		theirProps: l,
		slot: g,
		defaultTag: Je$1,
		features: qe$3,
		visible: m,
		name: "Listbox.Options"
	});
}
var Ze$1 = "li";
function et$1(e, a) {
	let n = I$9(), { id: r = `headlessui-listbox-option-${n}`, disabled: l = !1, value: t, ...p } = e, u = w$1("Listbox.Option"), i = k("Listbox.Option"), b = u.activeOptionIndex !== null ? u.options[u.activeOptionIndex].id === r : !1, R = u.isSelected(t), m = (0, import_react.useRef)(null), P = s$2(m), S = s$13({
		disabled: l,
		value: t,
		domRef: m,
		get textValue() {
			return P();
		}
	}), g = y$3(a, m);
	l$10(() => {
		if (u.listboxState !== 0 || !b || u.activationTrigger === 0) return;
		let A = o$8();
		return A.requestAnimationFrame(() => {
			var d, H;
			(H = (d = m.current) == null ? void 0 : d.scrollIntoView) == null || H.call(d, { block: "nearest" });
		}), A.dispose;
	}, [
		m,
		b,
		u.listboxState,
		u.activationTrigger,
		u.activeOptionIndex
	]), l$10(() => i.registerOption(r, S), [S, r]);
	let x = o$10((A) => {
		if (l) return A.preventDefault();
		i.onChange(t), u.mode === 0 && (i.closeListbox(), o$8().nextFrame(() => {
			var d;
			return (d = u.buttonRef.current) == null ? void 0 : d.focus({ preventScroll: !0 });
		}));
	}), T = o$10(() => {
		if (l) return i.goToOption(c$9.Nothing);
		i.goToOption(c$9.Specific, r);
	}), o = u$9(), L = o$10((A) => o.update(A)), U = o$10((A) => {
		o.wasMoved(A) && (l || b || i.goToOption(c$9.Specific, r, 0));
	}), B = o$10((A) => {
		o.wasMoved(A) && (l || b && i.goToOption(c$9.Nothing));
	}), W = (0, import_react.useMemo)(() => ({
		active: b,
		selected: R,
		disabled: l
	}), [
		b,
		R,
		l
	]);
	return C$5({
		ourProps: {
			id: r,
			ref: g,
			role: "option",
			tabIndex: l === !0 ? void 0 : -1,
			"aria-disabled": l === !0 ? !0 : void 0,
			"aria-selected": R,
			disabled: void 0,
			onClick: x,
			onFocus: T,
			onPointerEnter: L,
			onMouseEnter: L,
			onPointerMove: U,
			onMouseMove: U,
			onPointerLeave: B,
			onMouseLeave: B
		},
		theirProps: p,
		slot: W,
		defaultTag: Ze$1,
		name: "Listbox.Option"
	});
}
var tt$1 = U$5(Qe$1), ot$1 = U$5(Xe$1), nt = U$5(ze$1), it$1 = U$5(Ye$1), rt = U$5(et$1), It = Object.assign(tt$1, {
	Button: ot$1,
	Label: nt,
	Options: it$1,
	Option: rt
});
//#endregion
//#region node_modules/@headlessui/react/dist/components/menu/menu.js
var me$1 = ((r) => (r[r.Open = 0] = "Open", r[r.Closed = 1] = "Closed", r))(me$1 || {}), de$3 = ((r) => (r[r.Pointer = 0] = "Pointer", r[r.Other = 1] = "Other", r))(de$3 || {}), fe$2 = ((a) => (a[a.OpenMenu = 0] = "OpenMenu", a[a.CloseMenu = 1] = "CloseMenu", a[a.GoToItem = 2] = "GoToItem", a[a.Search = 3] = "Search", a[a.ClearSearch = 4] = "ClearSearch", a[a.RegisterItem = 5] = "RegisterItem", a[a.UnregisterItem = 6] = "UnregisterItem", a))(fe$2 || {});
function w(e, u = (r) => r) {
	let r = e.activeItemIndex !== null ? e.items[e.activeItemIndex] : null, s = I$8(u(e.items.slice()), (t) => t.dataRef.current.domRef.current), i = r ? s.indexOf(r) : null;
	return i === -1 && (i = null), {
		items: s,
		activeItemIndex: i
	};
}
var Te$1 = {
	[1](e) {
		return e.menuState === 1 ? e : {
			...e,
			activeItemIndex: null,
			menuState: 1
		};
	},
	[0](e) {
		return e.menuState === 0 ? e : {
			...e,
			__demoMode: !1,
			menuState: 0
		};
	},
	[2]: (e, u) => {
		var i;
		let r = w(e), s = f$8(u, {
			resolveItems: () => r.items,
			resolveActiveIndex: () => r.activeItemIndex,
			resolveId: (t) => t.id,
			resolveDisabled: (t) => t.dataRef.current.disabled
		});
		return {
			...e,
			...r,
			searchQuery: "",
			activeItemIndex: s,
			activationTrigger: (i = u.trigger) != null ? i : 1
		};
	},
	[3]: (e, u) => {
		let s = e.searchQuery !== "" ? 0 : 1, i = e.searchQuery + u.value.toLowerCase(), o = (e.activeItemIndex !== null ? e.items.slice(e.activeItemIndex + s).concat(e.items.slice(0, e.activeItemIndex + s)) : e.items).find((l) => {
			var m;
			return ((m = l.dataRef.current.textValue) == null ? void 0 : m.startsWith(i)) && !l.dataRef.current.disabled;
		}), a = o ? e.items.indexOf(o) : -1;
		return a === -1 || a === e.activeItemIndex ? {
			...e,
			searchQuery: i
		} : {
			...e,
			searchQuery: i,
			activeItemIndex: a,
			activationTrigger: 1
		};
	},
	[4](e) {
		return e.searchQuery === "" ? e : {
			...e,
			searchQuery: "",
			searchActiveItemIndex: null
		};
	},
	[5]: (e, u) => {
		let r = w(e, (s) => [...s, {
			id: u.id,
			dataRef: u.dataRef
		}]);
		return {
			...e,
			...r
		};
	},
	[6]: (e, u) => {
		let r = w(e, (s) => {
			let i = s.findIndex((t) => t.id === u.id);
			return i !== -1 && s.splice(i, 1), s;
		});
		return {
			...e,
			...r,
			activationTrigger: 1
		};
	}
}, U$2 = (0, import_react.createContext)(null);
U$2.displayName = "MenuContext";
function C$3(e) {
	let u = (0, import_react.useContext)(U$2);
	if (u === null) {
		let r = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Menu /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(r, C$3), r;
	}
	return u;
}
function ye$2(e, u) {
	return u$11(u.type, Te$1, e, u);
}
var Ie$2 = import_react.Fragment;
function Me(e, u) {
	let { __demoMode: r = !1, ...s } = e, i = (0, import_react.useReducer)(ye$2, {
		__demoMode: r,
		menuState: r ? 0 : 1,
		buttonRef: (0, import_react.createRef)(),
		itemsRef: (0, import_react.createRef)(),
		items: [],
		searchQuery: "",
		activeItemIndex: null,
		activationTrigger: 1
	}), [{ menuState: t, itemsRef: o, buttonRef: a }, l] = i, m = y$3(u);
	y$4([a, o], (g, R) => {
		var p;
		l({ type: 1 }), h$7(R, T$4.Loose) || (g.preventDefault(), (p = a.current) == null || p.focus());
	}, t === 0);
	let I = o$10(() => {
		l({ type: 1 });
	}), A = (0, import_react.useMemo)(() => ({
		open: t === 0,
		close: I
	}), [t, I]), f = { ref: m };
	return import_react.createElement(U$2.Provider, { value: i }, import_react.createElement(s$6, { value: u$11(t, {
		[0]: d$10.Open,
		[1]: d$10.Closed
	}) }, C$5({
		ourProps: f,
		theirProps: s,
		slot: A,
		defaultTag: Ie$2,
		name: "Menu"
	})));
}
var ge$2 = "button";
function Re$2(e, u) {
	var R;
	let r = I$9(), { id: s = `headlessui-menu-button-${r}`, ...i } = e, [t, o] = C$3("Menu.Button"), a = y$3(t.buttonRef, u), l = p$5(), m = o$10((p) => {
		switch (p.key) {
			case o$1.Space:
			case o$1.Enter:
			case o$1.ArrowDown:
				p.preventDefault(), p.stopPropagation(), o({ type: 0 }), l.nextFrame(() => o({
					type: 2,
					focus: c$9.First
				}));
				break;
			case o$1.ArrowUp:
				p.preventDefault(), p.stopPropagation(), o({ type: 0 }), l.nextFrame(() => o({
					type: 2,
					focus: c$9.Last
				}));
				break;
		}
	}), I = o$10((p) => {
		switch (p.key) {
			case o$1.Space:
				p.preventDefault();
				break;
		}
	}), A = o$10((p) => {
		if (r$4(p.currentTarget)) return p.preventDefault();
		e.disabled || (t.menuState === 0 ? (o({ type: 1 }), l.nextFrame(() => {
			var M;
			return (M = t.buttonRef.current) == null ? void 0 : M.focus({ preventScroll: !0 });
		})) : (p.preventDefault(), o({ type: 0 })));
	}), f = (0, import_react.useMemo)(() => ({ open: t.menuState === 0 }), [t]);
	return C$5({
		ourProps: {
			ref: a,
			id: s,
			type: T$3(e, t.buttonRef),
			"aria-haspopup": "menu",
			"aria-controls": (R = t.itemsRef.current) == null ? void 0 : R.id,
			"aria-expanded": t.menuState === 0,
			onKeyDown: m,
			onKeyUp: I,
			onClick: A
		},
		theirProps: i,
		slot: f,
		defaultTag: ge$2,
		name: "Menu.Button"
	});
}
var Ae$2 = "div", be$1 = O$1.RenderStrategy | O$1.Static;
function Ee$2(e, u) {
	var M, b;
	let r = I$9(), { id: s = `headlessui-menu-items-${r}`, ...i } = e, [t, o] = C$3("Menu.Items"), a = y$3(t.itemsRef, u), l = n$4(t.itemsRef), m = p$5(), I = u$7(), A = (() => I !== null ? (I & d$10.Open) === d$10.Open : t.menuState === 0)();
	(0, import_react.useEffect)(() => {
		let n = t.itemsRef.current;
		n && t.menuState === 0 && n !== (l == null ? void 0 : l.activeElement) && n.focus({ preventScroll: !0 });
	}, [
		t.menuState,
		t.itemsRef,
		l
	]), F$7({
		container: t.itemsRef.current,
		enabled: t.menuState === 0,
		accept(n) {
			return n.getAttribute("role") === "menuitem" ? NodeFilter.FILTER_REJECT : n.hasAttribute("role") ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT;
		},
		walk(n) {
			n.setAttribute("role", "none");
		}
	});
	let f = o$10((n) => {
		var E, x;
		switch (m.dispose(), n.key) {
			case o$1.Space: if (t.searchQuery !== "") return n.preventDefault(), n.stopPropagation(), o({
				type: 3,
				value: n.key
			});
			case o$1.Enter:
				if (n.preventDefault(), n.stopPropagation(), o({ type: 1 }), t.activeItemIndex !== null) {
					let { dataRef: S } = t.items[t.activeItemIndex];
					(x = (E = S.current) == null ? void 0 : E.domRef.current) == null || x.click();
				}
				D$5(t.buttonRef.current);
				break;
			case o$1.ArrowDown: return n.preventDefault(), n.stopPropagation(), o({
				type: 2,
				focus: c$9.Next
			});
			case o$1.ArrowUp: return n.preventDefault(), n.stopPropagation(), o({
				type: 2,
				focus: c$9.Previous
			});
			case o$1.Home:
			case o$1.PageUp: return n.preventDefault(), n.stopPropagation(), o({
				type: 2,
				focus: c$9.First
			});
			case o$1.End:
			case o$1.PageDown: return n.preventDefault(), n.stopPropagation(), o({
				type: 2,
				focus: c$9.Last
			});
			case o$1.Escape:
				n.preventDefault(), n.stopPropagation(), o({ type: 1 }), o$8().nextFrame(() => {
					var S;
					return (S = t.buttonRef.current) == null ? void 0 : S.focus({ preventScroll: !0 });
				});
				break;
			case o$1.Tab:
				n.preventDefault(), n.stopPropagation(), o({ type: 1 }), o$8().nextFrame(() => {
					_$3(t.buttonRef.current, n.shiftKey ? M$5.Previous : M$5.Next);
				});
				break;
			default:
				n.key.length === 1 && (o({
					type: 3,
					value: n.key
				}), m.setTimeout(() => o({ type: 4 }), 350));
				break;
		}
	}), g = o$10((n) => {
		switch (n.key) {
			case o$1.Space:
				n.preventDefault();
				break;
		}
	}), R = (0, import_react.useMemo)(() => ({ open: t.menuState === 0 }), [t]);
	return C$5({
		ourProps: {
			"aria-activedescendant": t.activeItemIndex === null || (M = t.items[t.activeItemIndex]) == null ? void 0 : M.id,
			"aria-labelledby": (b = t.buttonRef.current) == null ? void 0 : b.id,
			id: s,
			onKeyDown: f,
			onKeyUp: g,
			role: "menu",
			tabIndex: 0,
			ref: a
		},
		theirProps: i,
		slot: R,
		defaultTag: Ae$2,
		features: be$1,
		visible: A,
		name: "Menu.Items"
	});
}
var Se$3 = import_react.Fragment;
function xe$3(e, u) {
	let r = I$9(), { id: s = `headlessui-menu-item-${r}`, disabled: i = !1, ...t } = e, [o, a] = C$3("Menu.Item"), l = o.activeItemIndex !== null ? o.items[o.activeItemIndex].id === s : !1, m = (0, import_react.useRef)(null), I = y$3(u, m);
	l$10(() => {
		if (o.__demoMode || o.menuState !== 0 || !l || o.activationTrigger === 0) return;
		let T = o$8();
		return T.requestAnimationFrame(() => {
			var P, B;
			(B = (P = m.current) == null ? void 0 : P.scrollIntoView) == null || B.call(P, { block: "nearest" });
		}), T.dispose;
	}, [
		o.__demoMode,
		m,
		l,
		o.menuState,
		o.activationTrigger,
		o.activeItemIndex
	]);
	let A = s$2(m), f = (0, import_react.useRef)({
		disabled: i,
		domRef: m,
		get textValue() {
			return A();
		}
	});
	l$10(() => {
		f.current.disabled = i;
	}, [f, i]), l$10(() => (a({
		type: 5,
		id: s,
		dataRef: f
	}), () => a({
		type: 6,
		id: s
	})), [f, s]);
	let g = o$10(() => {
		a({ type: 1 });
	}), R = o$10((T) => {
		if (i) return T.preventDefault();
		a({ type: 1 }), D$5(o.buttonRef.current);
	}), p = o$10(() => {
		if (i) return a({
			type: 2,
			focus: c$9.Nothing
		});
		a({
			type: 2,
			focus: c$9.Specific,
			id: s
		});
	}), M = u$9(), b = o$10((T) => M.update(T)), n = o$10((T) => {
		M.wasMoved(T) && (i || l || a({
			type: 2,
			focus: c$9.Specific,
			id: s,
			trigger: 0
		}));
	}), E = o$10((T) => {
		M.wasMoved(T) && (i || l && a({
			type: 2,
			focus: c$9.Nothing
		}));
	}), x = (0, import_react.useMemo)(() => ({
		active: l,
		disabled: i,
		close: g
	}), [
		l,
		i,
		g
	]);
	return C$5({
		ourProps: {
			id: s,
			ref: I,
			role: "menuitem",
			tabIndex: i === !0 ? void 0 : -1,
			"aria-disabled": i === !0 ? !0 : void 0,
			disabled: void 0,
			onClick: R,
			onFocus: p,
			onPointerEnter: b,
			onMouseEnter: b,
			onPointerMove: n,
			onMouseMove: n,
			onPointerLeave: E,
			onMouseLeave: E
		},
		theirProps: t,
		slot: x,
		defaultTag: Se$3,
		name: "Menu.Item"
	});
}
var Pe$3 = U$5(Me), ve = U$5(Re$2), he$3 = U$5(Ee$2), De$2 = U$5(xe$3), qe = Object.assign(Pe$3, {
	Button: ve,
	Items: he$3,
	Item: De$2
});
//#endregion
//#region node_modules/@headlessui/react/dist/components/popover/popover.js
var he$2 = ((u) => (u[u.Open = 0] = "Open", u[u.Closed = 1] = "Closed", u))(he$2 || {}), He$1 = ((e) => (e[e.TogglePopover = 0] = "TogglePopover", e[e.ClosePopover = 1] = "ClosePopover", e[e.SetButton = 2] = "SetButton", e[e.SetButtonId = 3] = "SetButtonId", e[e.SetPanel = 4] = "SetPanel", e[e.SetPanelId = 5] = "SetPanelId", e))(He$1 || {});
var Ge$1 = {
	[0]: (t) => {
		let o = {
			...t,
			popoverState: u$11(t.popoverState, {
				[0]: 1,
				[1]: 0
			})
		};
		return o.popoverState === 0 && (o.__demoMode = !1), o;
	},
	[1](t) {
		return t.popoverState === 1 ? t : {
			...t,
			popoverState: 1
		};
	},
	[2](t, o) {
		return t.button === o.button ? t : {
			...t,
			button: o.button
		};
	},
	[3](t, o) {
		return t.buttonId === o.buttonId ? t : {
			...t,
			buttonId: o.buttonId
		};
	},
	[4](t, o) {
		return t.panel === o.panel ? t : {
			...t,
			panel: o.panel
		};
	},
	[5](t, o) {
		return t.panelId === o.panelId ? t : {
			...t,
			panelId: o.panelId
		};
	}
}, ue$3 = (0, import_react.createContext)(null);
ue$3.displayName = "PopoverContext";
function oe$2(t) {
	let o = (0, import_react.useContext)(ue$3);
	if (o === null) {
		let u = /* @__PURE__ */ new Error(`<${t} /> is missing a parent <Popover /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(u, oe$2), u;
	}
	return o;
}
var ie = (0, import_react.createContext)(null);
ie.displayName = "PopoverAPIContext";
function fe$1(t) {
	let o = (0, import_react.useContext)(ie);
	if (o === null) {
		let u = /* @__PURE__ */ new Error(`<${t} /> is missing a parent <Popover /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(u, fe$1), u;
	}
	return o;
}
var Pe$2 = (0, import_react.createContext)(null);
Pe$2.displayName = "PopoverGroupContext";
function Ee$1() {
	return (0, import_react.useContext)(Pe$2);
}
var re$2 = (0, import_react.createContext)(null);
re$2.displayName = "PopoverPanelContext";
function Ne$1() {
	return (0, import_react.useContext)(re$2);
}
function ke$1(t, o) {
	return u$11(o.type, Ge$1, t, o);
}
var we$1 = "div";
function Ue(t, o) {
	var B;
	let { __demoMode: u = !1, ...M } = t, x = (0, import_react.useRef)(null), n = y$3(o, T$2((l) => {
		x.current = l;
	})), e = (0, import_react.useRef)([]), c = (0, import_react.useReducer)(ke$1, {
		__demoMode: u,
		popoverState: u ? 0 : 1,
		buttons: e,
		button: null,
		buttonId: null,
		panel: null,
		panelId: null,
		beforePanelSentinel: (0, import_react.createRef)(),
		afterPanelSentinel: (0, import_react.createRef)()
	}), [{ popoverState: f, button: s, buttonId: I, panel: a, panelId: v, beforePanelSentinel: y, afterPanelSentinel: A }, P] = c, p = n$4((B = x.current) != null ? B : s), E = (0, import_react.useMemo)(() => {
		if (!s || !a) return !1;
		for (let W of document.querySelectorAll("body > *")) if (Number(W == null ? void 0 : W.contains(s)) ^ Number(W == null ? void 0 : W.contains(a))) return !0;
		let l = f$11(), S = l.indexOf(s), q = (S + l.length - 1) % l.length, U = (S + 1) % l.length, z = l[q], be = l[U];
		return !a.contains(z) && !a.contains(be);
	}, [s, a]), F = s$13(I), D = s$13(v), _ = (0, import_react.useMemo)(() => ({
		buttonId: F,
		panelId: D,
		close: () => P({ type: 1 })
	}), [
		F,
		D,
		P
	]), O = Ee$1(), L = O == null ? void 0 : O.registerPopover, $ = o$10(() => {
		var l;
		return (l = O == null ? void 0 : O.isFocusWithinPopoverGroup()) != null ? l : (p == null ? void 0 : p.activeElement) && ((s == null ? void 0 : s.contains(p.activeElement)) || (a == null ? void 0 : a.contains(p.activeElement)));
	});
	(0, import_react.useEffect)(() => L == null ? void 0 : L(_), [L, _]);
	let [i, b] = ee$5(), T = N$2({
		mainTreeNodeRef: O == null ? void 0 : O.mainTreeNodeRef,
		portals: i,
		defaultContainers: [s, a]
	});
	E$4(p == null ? void 0 : p.defaultView, "focus", (l) => {
		var S, q, U, z;
		l.target !== window && l.target instanceof HTMLElement && f === 0 && ($() || s && a && (T.contains(l.target) || (q = (S = y.current) == null ? void 0 : S.contains) != null && q.call(S, l.target) || (z = (U = A.current) == null ? void 0 : U.contains) != null && z.call(U, l.target) || P({ type: 1 })));
	}, !0), y$4(T.resolveContainers, (l, S) => {
		P({ type: 1 }), h$7(S, T$4.Loose) || (l.preventDefault(), s?.focus());
	}, f === 0);
	let d = o$10((l) => {
		P({ type: 1 });
		(() => l ? l instanceof HTMLElement ? l : "current" in l && l.current instanceof HTMLElement ? l.current : s : s)()?.focus();
	}), r = (0, import_react.useMemo)(() => ({
		close: d,
		isPortalled: E
	}), [d, E]), m = (0, import_react.useMemo)(() => ({
		open: f === 0,
		close: d
	}), [f, d]), g = { ref: n };
	return import_react.createElement(re$2.Provider, { value: null }, import_react.createElement(ue$3.Provider, { value: c }, import_react.createElement(ie.Provider, { value: r }, import_react.createElement(s$6, { value: u$11(f, {
		[0]: d$10.Open,
		[1]: d$10.Closed
	}) }, import_react.createElement(b, null, C$5({
		ourProps: g,
		theirProps: M,
		slot: m,
		defaultTag: we$1,
		name: "Popover"
	}), import_react.createElement(T.MainTreeNode, null))))));
}
var We = "button";
function Ke(t, o) {
	let u = I$9(), { id: M = `headlessui-popover-button-${u}`, ...x } = t, [n, e] = oe$2("Popover.Button"), { isPortalled: c } = fe$1("Popover.Button"), f = (0, import_react.useRef)(null), s = `headlessui-focus-sentinel-${I$9()}`, I = Ee$1(), a = I == null ? void 0 : I.closeOthers, y = Ne$1() !== null;
	(0, import_react.useEffect)(() => {
		if (!y) return e({
			type: 3,
			buttonId: M
		}), () => {
			e({
				type: 3,
				buttonId: null
			});
		};
	}, [
		y,
		M,
		e
	]);
	let [A] = (0, import_react.useState)(() => Symbol()), P = y$3(f, o, y ? null : (r) => {
		if (r) n.buttons.current.push(A);
		else {
			let m = n.buttons.current.indexOf(A);
			m !== -1 && n.buttons.current.splice(m, 1);
		}
		n.buttons.current.length > 1 && console.warn("You are already using a <Popover.Button /> but only 1 <Popover.Button /> is supported."), r && e({
			type: 2,
			button: r
		});
	}), p = y$3(f, o), E = n$4(f), F = o$10((r) => {
		var m, g, B;
		if (y) {
			if (n.popoverState === 1) return;
			switch (r.key) {
				case o$1.Space:
				case o$1.Enter:
					r.preventDefault(), (g = (m = r.target).click) == null || g.call(m), e({ type: 1 }), (B = n.button) == null || B.focus();
					break;
			}
		} else switch (r.key) {
			case o$1.Space:
			case o$1.Enter:
				r.preventDefault(), r.stopPropagation(), n.popoverState === 1 && a?.(n.buttonId), e({ type: 0 });
				break;
			case o$1.Escape:
				if (n.popoverState !== 0) return a == null ? void 0 : a(n.buttonId);
				if (!f.current || E != null && E.activeElement && !f.current.contains(E.activeElement)) return;
				r.preventDefault(), r.stopPropagation(), e({ type: 1 });
				break;
		}
	}), D = o$10((r) => {
		y || r.key === o$1.Space && r.preventDefault();
	}), _ = o$10((r) => {
		var m, g;
		r$4(r.currentTarget) || t.disabled || (y ? (e({ type: 1 }), (m = n.button) == null || m.focus()) : (r.preventDefault(), r.stopPropagation(), n.popoverState === 1 && a?.(n.buttonId), e({ type: 0 }), (g = n.button) == null || g.focus()));
	}), O = o$10((r) => {
		r.preventDefault(), r.stopPropagation();
	}), L = n.popoverState === 0, $ = (0, import_react.useMemo)(() => ({ open: L }), [L]), i = T$3(t, f), b = y ? {
		ref: p,
		type: i,
		onKeyDown: F,
		onClick: _
	} : {
		ref: P,
		id: n.buttonId,
		type: i,
		"aria-expanded": n.popoverState === 0,
		"aria-controls": n.panel ? n.panelId : void 0,
		onKeyDown: F,
		onKeyUp: D,
		onClick: _,
		onMouseDown: O
	}, T = n$1(), d = o$10(() => {
		let r = n.panel;
		if (!r) return;
		function m() {
			u$11(T.current, {
				[s$5.Forwards]: () => O$2(r, M$5.First),
				[s$5.Backwards]: () => O$2(r, M$5.Last)
			}) === N$5.Error && O$2(f$11().filter((B) => B.dataset.headlessuiFocusGuard !== "true"), u$11(T.current, {
				[s$5.Forwards]: M$5.Next,
				[s$5.Backwards]: M$5.Previous
			}), { relativeTo: n.button });
		}
		m();
	});
	return import_react.createElement(import_react.Fragment, null, C$5({
		ourProps: b,
		theirProps: x,
		slot: $,
		defaultTag: We,
		name: "Popover.Button"
	}), L && !y && c && import_react.createElement(u$8, {
		id: s,
		features: s$7.Focusable,
		"data-headlessui-focus-guard": !0,
		as: "button",
		type: "button",
		onFocus: d
	}));
}
var je = "div", Ve = O$1.RenderStrategy | O$1.Static;
function $e$1(t, o) {
	let u = I$9(), { id: M = `headlessui-popover-overlay-${u}`, ...x } = t, [{ popoverState: n }, e] = oe$2("Popover.Overlay"), c = y$3(o), f = u$7(), s = (() => f !== null ? (f & d$10.Open) === d$10.Open : n === 0)(), I = o$10((y) => {
		if (r$4(y.currentTarget)) return y.preventDefault();
		e({ type: 1 });
	}), a = (0, import_react.useMemo)(() => ({ open: n === 0 }), [n]);
	return C$5({
		ourProps: {
			ref: c,
			id: M,
			"aria-hidden": !0,
			onClick: I
		},
		theirProps: x,
		slot: a,
		defaultTag: je,
		features: Ve,
		visible: s,
		name: "Popover.Overlay"
	});
}
var Je = "div", Xe = O$1.RenderStrategy | O$1.Static;
function Ye(t, o) {
	let u = I$9(), { id: M = `headlessui-popover-panel-${u}`, focus: x = !1, ...n } = t, [e, c] = oe$2("Popover.Panel"), { close: f, isPortalled: s } = fe$1("Popover.Panel"), I = `headlessui-focus-sentinel-before-${I$9()}`, a = `headlessui-focus-sentinel-after-${I$9()}`, v = (0, import_react.useRef)(null), y = y$3(v, o, (i) => {
		c({
			type: 4,
			panel: i
		});
	}), A = n$4(v), P = I$7();
	l$10(() => (c({
		type: 5,
		panelId: M
	}), () => {
		c({
			type: 5,
			panelId: null
		});
	}), [M, c]);
	let p = u$7(), E = (() => p !== null ? (p & d$10.Open) === d$10.Open : e.popoverState === 0)(), F = o$10((i) => {
		var b;
		switch (i.key) {
			case o$1.Escape:
				if (e.popoverState !== 0 || !v.current || A != null && A.activeElement && !v.current.contains(A.activeElement)) return;
				i.preventDefault(), i.stopPropagation(), c({ type: 1 }), (b = e.button) == null || b.focus();
				break;
		}
	});
	(0, import_react.useEffect)(() => {
		var i;
		t.static || e.popoverState === 1 && ((i = t.unmount) == null || i) && c({
			type: 4,
			panel: null
		});
	}, [
		e.popoverState,
		t.unmount,
		t.static,
		c
	]), (0, import_react.useEffect)(() => {
		if (e.__demoMode || !x || e.popoverState !== 0 || !v.current) return;
		let i = A == null ? void 0 : A.activeElement;
		v.current.contains(i) || O$2(v.current, M$5.First);
	}, [
		e.__demoMode,
		x,
		v,
		e.popoverState
	]);
	let D = (0, import_react.useMemo)(() => ({
		open: e.popoverState === 0,
		close: f
	}), [e, f]), _ = {
		ref: y,
		id: M,
		onKeyDown: F,
		onBlur: x && e.popoverState === 0 ? (i) => {
			var T, d, r, m, g;
			let b = i.relatedTarget;
			b && v.current && ((T = v.current) != null && T.contains(b) || (c({ type: 1 }), ((r = (d = e.beforePanelSentinel.current) == null ? void 0 : d.contains) != null && r.call(d, b) || (g = (m = e.afterPanelSentinel.current) == null ? void 0 : m.contains) != null && g.call(m, b)) && b.focus({ preventScroll: !0 })));
		} : void 0,
		tabIndex: -1
	}, O = n$1(), L = o$10(() => {
		let i = v.current;
		if (!i) return;
		function b() {
			u$11(O.current, {
				[s$5.Forwards]: () => {
					var d;
					O$2(i, M$5.First) === N$5.Error && ((d = e.afterPanelSentinel.current) == null || d.focus());
				},
				[s$5.Backwards]: () => {
					var T;
					(T = e.button) == null || T.focus({ preventScroll: !0 });
				}
			});
		}
		b();
	}), $ = o$10(() => {
		let i = v.current;
		if (!i) return;
		function b() {
			u$11(O.current, {
				[s$5.Forwards]: () => {
					var B;
					if (!e.button) return;
					let T = f$11(), d = T.indexOf(e.button), r = T.slice(0, d + 1), g = [...T.slice(d + 1), ...r];
					for (let l of g.slice()) if (l.dataset.headlessuiFocusGuard === "true" || (B = e.panel) != null && B.contains(l)) {
						let S = g.indexOf(l);
						S !== -1 && g.splice(S, 1);
					}
					O$2(g, M$5.First, { sorted: !1 });
				},
				[s$5.Backwards]: () => {
					var d;
					O$2(i, M$5.Previous) === N$5.Error && ((d = e.button) == null || d.focus());
				}
			});
		}
		b();
	});
	return import_react.createElement(re$2.Provider, { value: M }, E && s && import_react.createElement(u$8, {
		id: I,
		ref: e.beforePanelSentinel,
		features: s$7.Focusable,
		"data-headlessui-focus-guard": !0,
		as: "button",
		type: "button",
		onFocus: L
	}), C$5({
		mergeRefs: P,
		ourProps: _,
		theirProps: n,
		slot: D,
		defaultTag: Je,
		features: Xe,
		visible: E,
		name: "Popover.Panel"
	}), E && s && import_react.createElement(u$8, {
		id: a,
		ref: e.afterPanelSentinel,
		features: s$7.Focusable,
		"data-headlessui-focus-guard": !0,
		as: "button",
		type: "button",
		onFocus: $
	}));
}
var qe$2 = "div";
function ze(t, o) {
	let u = (0, import_react.useRef)(null), M = y$3(u, o), [x, n] = (0, import_react.useState)([]), e = y$1(), c = o$10((P) => {
		n((p) => {
			let E = p.indexOf(P);
			if (E !== -1) {
				let F = p.slice();
				return F.splice(E, 1), F;
			}
			return p;
		});
	}), f = o$10((P) => (n((p) => [...p, P]), () => c(P))), s = o$10(() => {
		var E;
		let P = o$5(u);
		if (!P) return !1;
		let p = P.activeElement;
		return (E = u.current) != null && E.contains(p) ? !0 : x.some((F) => {
			var D, _;
			return ((D = P.getElementById(F.buttonId.current)) == null ? void 0 : D.contains(p)) || ((_ = P.getElementById(F.panelId.current)) == null ? void 0 : _.contains(p));
		});
	}), I = o$10((P) => {
		for (let p of x) p.buttonId.current !== P && p.close();
	}), a = (0, import_react.useMemo)(() => ({
		registerPopover: f,
		unregisterPopover: c,
		isFocusWithinPopoverGroup: s,
		closeOthers: I,
		mainTreeNodeRef: e.mainTreeNodeRef
	}), [
		f,
		c,
		s,
		I,
		e.mainTreeNodeRef
	]), v = (0, import_react.useMemo)(() => ({}), []), y = t, A = { ref: M };
	return import_react.createElement(Pe$2.Provider, { value: a }, C$5({
		ourProps: A,
		theirProps: y,
		slot: v,
		defaultTag: qe$2,
		name: "Popover.Group"
	}), import_react.createElement(e.MainTreeNode, null));
}
var Qe = U$5(Ue), Ze = U$5(Ke), et = U$5($e$1), tt = U$5(Ye), ot = U$5(ze), Ct = Object.assign(Qe, {
	Button: Ze,
	Overlay: et,
	Panel: tt,
	Group: ot
});
//#endregion
//#region node_modules/@headlessui/react/dist/components/label/label.js
var d$1 = (0, import_react.createContext)(null);
function u() {
	let a = (0, import_react.useContext)(d$1);
	if (a === null) {
		let t = /* @__PURE__ */ new Error("You used a <Label /> component, but it is not inside a relevant parent.");
		throw Error.captureStackTrace && Error.captureStackTrace(t, u), t;
	}
	return a;
}
function F$3() {
	let [a, t] = (0, import_react.useState)([]);
	return [a.length > 0 ? a.join(" ") : void 0, (0, import_react.useMemo)(() => function(e) {
		let s = o$10((r) => (t((l) => [...l, r]), () => t((l) => {
			let n = l.slice(), p = n.indexOf(r);
			return p !== -1 && n.splice(p, 1), n;
		}))), o = (0, import_react.useMemo)(() => ({
			register: s,
			slot: e.slot,
			name: e.name,
			props: e.props
		}), [
			s,
			e.slot,
			e.name,
			e.props
		]);
		return import_react.createElement(d$1.Provider, { value: o }, e.children);
	}, [t])];
}
var A$1 = "label";
function h(a, t) {
	let i = I$9(), { id: e = `headlessui-label-${i}`, passive: s = !1, ...o } = a, r = u(), l = y$3(t);
	l$10(() => r.register(e), [e, r.register]);
	let n = {
		ref: l,
		...r.props,
		id: e
	};
	return s && ("onClick" in n && (delete n.htmlFor, delete n.onClick), "onClick" in o && delete o.onClick), C$5({
		ourProps: n,
		theirProps: o,
		slot: r.slot || {},
		defaultTag: A$1,
		name: r.name || "Label"
	});
}
var v$1 = U$5(h), B$1 = Object.assign(v$1, {});
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-flags.js
function c$2(a = 0) {
	let [l, r] = (0, import_react.useState)(a), t = f$6();
	return {
		flags: l,
		addFlag: (0, import_react.useCallback)((e) => {
			t.current && r((u) => u | e);
		}, [l, t]),
		hasFlag: (0, import_react.useCallback)((e) => Boolean(l & e), [l]),
		removeFlag: (0, import_react.useCallback)((e) => {
			t.current && r((u) => u & ~e);
		}, [r, t]),
		toggleFlag: (0, import_react.useCallback)((e) => {
			t.current && r((u) => u ^ e);
		}, [r])
	};
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/radio-group/radio-group.js
var Ge = ((t) => (t[t.RegisterOption = 0] = "RegisterOption", t[t.UnregisterOption = 1] = "UnregisterOption", t))(Ge || {});
var Ce = {
	[0](o, r) {
		let t = [...o.options, {
			id: r.id,
			element: r.element,
			propsRef: r.propsRef
		}];
		return {
			...o,
			options: I$8(t, (p) => p.element.current)
		};
	},
	[1](o, r) {
		let t = o.options.slice(), p = o.options.findIndex((T) => T.id === r.id);
		return p === -1 ? o : (t.splice(p, 1), {
			...o,
			options: t
		});
	}
}, B = (0, import_react.createContext)(null);
B.displayName = "RadioGroupDataContext";
function oe$1(o) {
	let r = (0, import_react.useContext)(B);
	if (r === null) {
		let t = /* @__PURE__ */ new Error(`<${o} /> is missing a parent <RadioGroup /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(t, oe$1), t;
	}
	return r;
}
var $$2 = (0, import_react.createContext)(null);
$$2.displayName = "RadioGroupActionsContext";
function ne$2(o) {
	let r = (0, import_react.useContext)($$2);
	if (r === null) {
		let t = /* @__PURE__ */ new Error(`<${o} /> is missing a parent <RadioGroup /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(t, ne$2), t;
	}
	return r;
}
function ke(o, r) {
	return u$11(r.type, Ce, o, r);
}
var Le$2 = "div";
function he$1(o, r) {
	let t = I$9(), { id: p = `headlessui-radiogroup-${t}`, value: T, defaultValue: v, form: M, name: m, onChange: H, by: G = (e, i) => e === i, disabled: P = !1, ...N } = o, y = o$10(typeof G == "string" ? (e, i) => {
		let n = G;
		return (e == null ? void 0 : e[n]) === (i == null ? void 0 : i[n]);
	} : G), [A, L] = (0, import_react.useReducer)(ke, { options: [] }), a = A.options, [h, R] = F$3(), [C, U] = w$2(), k = (0, import_react.useRef)(null), W = y$3(k, r), [l, s] = T$5(T, H, v), b = (0, import_react.useMemo)(() => a.find((e) => !e.propsRef.current.disabled), [a]), x = (0, import_react.useMemo)(() => a.some((e) => y(e.propsRef.current.value, l)), [a, l]), d = o$10((e) => {
		var n;
		if (P || y(e, l)) return !1;
		let i = (n = a.find((f) => y(f.propsRef.current.value, e))) == null ? void 0 : n.propsRef.current;
		return i != null && i.disabled ? !1 : (s?.(e), !0);
	});
	F$7({
		container: k.current,
		accept(e) {
			return e.getAttribute("role") === "radio" ? NodeFilter.FILTER_REJECT : e.hasAttribute("role") ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT;
		},
		walk(e) {
			e.setAttribute("role", "none");
		}
	});
	let F = o$10((e) => {
		let i = k.current;
		if (!i) return;
		let n = o$5(i), f = a.filter((u) => u.propsRef.current.disabled === !1).map((u) => u.element.current);
		switch (e.key) {
			case o$1.Enter:
				p$2(e.currentTarget);
				break;
			case o$1.ArrowLeft:
			case o$1.ArrowUp:
				if (e.preventDefault(), e.stopPropagation(), O$2(f, M$5.Previous | M$5.WrapAround) === N$5.Success) {
					let g = a.find((K) => K.element.current === (n == null ? void 0 : n.activeElement));
					g && d(g.propsRef.current.value);
				}
				break;
			case o$1.ArrowRight:
			case o$1.ArrowDown:
				if (e.preventDefault(), e.stopPropagation(), O$2(f, M$5.Next | M$5.WrapAround) === N$5.Success) {
					let g = a.find((K) => K.element.current === (n == null ? void 0 : n.activeElement));
					g && d(g.propsRef.current.value);
				}
				break;
			case o$1.Space:
				{
					e.preventDefault(), e.stopPropagation();
					let u = a.find((g) => g.element.current === (n == null ? void 0 : n.activeElement));
					u && d(u.propsRef.current.value);
				}
				break;
		}
	}), c = o$10((e) => (L({
		type: 0,
		...e
	}), () => L({
		type: 1,
		id: e.id
	}))), w = (0, import_react.useMemo)(() => ({
		value: l,
		firstOption: b,
		containsCheckedOption: x,
		disabled: P,
		compare: y,
		...A
	}), [
		l,
		b,
		x,
		P,
		y,
		A
	]), ie = (0, import_react.useMemo)(() => ({
		registerOption: c,
		change: d
	}), [c, d]), ae = {
		ref: W,
		id: p,
		role: "radiogroup",
		"aria-labelledby": h,
		"aria-describedby": C,
		onKeyDown: F
	}, pe = (0, import_react.useMemo)(() => ({ value: l }), [l]), I = (0, import_react.useRef)(null), le = p$5();
	return (0, import_react.useEffect)(() => {
		I.current && v !== void 0 && le.addEventListener(I.current, "reset", () => {
			d(v);
		});
	}, [I, d]), import_react.createElement(U, { name: "RadioGroup.Description" }, import_react.createElement(R, { name: "RadioGroup.Label" }, import_react.createElement($$2.Provider, { value: ie }, import_react.createElement(B.Provider, { value: w }, m != null && l != null && e$1({ [m]: l }).map(([e, i], n) => import_react.createElement(u$8, {
		features: s$7.Hidden,
		ref: n === 0 ? (f) => {
			var u;
			I.current = (u = f == null ? void 0 : f.closest("form")) != null ? u : null;
		} : void 0,
		...x$2({
			key: e,
			as: "input",
			type: "radio",
			checked: i != null,
			hidden: !0,
			readOnly: !0,
			form: M,
			disabled: P,
			name: e,
			value: i
		})
	})), C$5({
		ourProps: ae,
		theirProps: N,
		slot: pe,
		defaultTag: Le$2,
		name: "RadioGroup"
	})))));
}
var xe$2 = ((t) => (t[t.Empty = 1] = "Empty", t[t.Active = 2] = "Active", t))(xe$2 || {});
var Fe$2 = "div";
function we(o, r) {
	var F;
	let t = I$9(), { id: p = `headlessui-radiogroup-option-${t}`, value: T, disabled: v = !1, ...M } = o, m = (0, import_react.useRef)(null), H = y$3(m, r), [G, P] = F$3(), [N, y] = w$2(), { addFlag: A, removeFlag: L, hasFlag: a } = c$2(1), h = s$13({
		value: T,
		disabled: v
	}), R = oe$1("RadioGroup.Option"), C = ne$2("RadioGroup.Option");
	l$10(() => C.registerOption({
		id: p,
		element: m,
		propsRef: h
	}), [
		p,
		C,
		m,
		h
	]);
	let U = o$10((c) => {
		var w;
		if (r$4(c.currentTarget)) return c.preventDefault();
		C.change(T) && (A(2), (w = m.current) == null || w.focus());
	}), k = o$10((c) => {
		if (r$4(c.currentTarget)) return c.preventDefault();
		A(2);
	}), W = o$10(() => L(2)), l = ((F = R.firstOption) == null ? void 0 : F.id) === p, s = R.disabled || v, b = R.compare(R.value, T), x = {
		ref: H,
		id: p,
		role: "radio",
		"aria-checked": b ? "true" : "false",
		"aria-labelledby": G,
		"aria-describedby": N,
		"aria-disabled": s ? !0 : void 0,
		tabIndex: (() => s ? -1 : b || !R.containsCheckedOption && l ? 0 : -1)(),
		onClick: s ? void 0 : U,
		onFocus: s ? void 0 : k,
		onBlur: s ? void 0 : W
	}, d = (0, import_react.useMemo)(() => ({
		checked: b,
		disabled: s,
		active: a(2)
	}), [
		b,
		s,
		a
	]);
	return import_react.createElement(y, { name: "RadioGroup.Description" }, import_react.createElement(P, { name: "RadioGroup.Label" }, C$5({
		ourProps: x,
		theirProps: M,
		slot: d,
		defaultTag: Fe$2,
		name: "RadioGroup.Option"
	})));
}
var Ie$1 = U$5(he$1), Se$2 = U$5(we), it = Object.assign(Ie$1, {
	Option: Se$2,
	Label: B$1,
	Description: G$2
});
//#endregion
//#region node_modules/@headlessui/react/dist/components/switch/switch.js
var S$1 = (0, import_react.createContext)(null);
S$1.displayName = "GroupContext";
var ee$1 = import_react.Fragment;
function te$1(r) {
	var u;
	let [n, p] = (0, import_react.useState)(null), [c, T] = F$3(), [o, b] = w$2(), a = (0, import_react.useMemo)(() => ({
		switch: n,
		setSwitch: p,
		labelledby: c,
		describedby: o
	}), [
		n,
		p,
		c,
		o
	]), d = {}, y = r;
	return import_react.createElement(b, { name: "Switch.Description" }, import_react.createElement(T, {
		name: "Switch.Label",
		props: {
			htmlFor: (u = a.switch) == null ? void 0 : u.id,
			onClick(m) {
				n && (m.currentTarget.tagName === "LABEL" && m.preventDefault(), n.click(), n.focus({ preventScroll: !0 }));
			}
		}
	}, import_react.createElement(S$1.Provider, { value: a }, C$5({
		ourProps: d,
		theirProps: y,
		defaultTag: ee$1,
		name: "Switch.Group"
	}))));
}
var ne$1 = "button";
function re$1(r, n) {
	var E;
	let p = I$9(), { id: c = `headlessui-switch-${p}`, checked: T, defaultChecked: o = !1, onChange: b, disabled: a = !1, name: d, value: y, form: u, ...m } = r, t = (0, import_react.useContext)(S$1), f = (0, import_react.useRef)(null), C = y$3(f, n, t === null ? null : t.setSwitch), [i, s] = T$5(T, b, o), w = o$10(() => s == null ? void 0 : s(!i)), L = o$10((e) => {
		if (r$4(e.currentTarget)) return e.preventDefault();
		e.preventDefault(), w();
	}), x = o$10((e) => {
		e.key === o$1.Space ? (e.preventDefault(), w()) : e.key === o$1.Enter && p$2(e.currentTarget);
	}), v = o$10((e) => e.preventDefault()), G = (0, import_react.useMemo)(() => ({ checked: i }), [i]), R = {
		id: c,
		ref: C,
		role: "switch",
		type: T$3(r, f),
		tabIndex: r.tabIndex === -1 ? 0 : (E = r.tabIndex) != null ? E : 0,
		"aria-checked": i,
		"aria-labelledby": t == null ? void 0 : t.labelledby,
		"aria-describedby": t == null ? void 0 : t.describedby,
		disabled: a,
		onClick: L,
		onKeyUp: x,
		onKeyPress: v
	}, k = p$5();
	return (0, import_react.useEffect)(() => {
		var _;
		let e = (_ = f.current) == null ? void 0 : _.closest("form");
		e && o !== void 0 && k.addEventListener(e, "reset", () => {
			s(o);
		});
	}, [f, s]), import_react.createElement(import_react.Fragment, null, d != null && i && import_react.createElement(u$8, {
		features: s$7.Hidden,
		...x$2({
			as: "input",
			type: "checkbox",
			hidden: !0,
			readOnly: !0,
			disabled: a,
			form: u,
			checked: i,
			name: d,
			value: y
		})
	}), C$5({
		ourProps: R,
		theirProps: m,
		slot: G,
		defaultTag: ne$1,
		name: "Switch"
	}));
}
var oe = U$5(re$1), _e = Object.assign(oe, {
	Group: te$1,
	Label: B$1,
	Description: G$2
});
//#endregion
//#region node_modules/@headlessui/react/dist/internal/focus-sentinel.js
function b$1({ onFocus: n }) {
	let [r, o] = (0, import_react.useState)(!0), u = f$6();
	return r ? import_react.createElement(u$8, {
		as: "button",
		type: "button",
		features: s$7.Focusable,
		onFocus: (a) => {
			a.preventDefault();
			let e, i = 50;
			function t() {
				if (i-- <= 0) {
					e && cancelAnimationFrame(e);
					return;
				}
				if (n()) {
					if (cancelAnimationFrame(e), !u.current) return;
					o(!1);
					return;
				}
				e = requestAnimationFrame(t);
			}
			e = requestAnimationFrame(t);
		}
	}) : null;
}
//#endregion
//#region node_modules/@headlessui/react/dist/utils/stable-collection.js
var s = import_react.createContext(null);
function a() {
	return {
		groups: /* @__PURE__ */ new Map(),
		get(n, t) {
			var c;
			let e = this.groups.get(n);
			e || (e = /* @__PURE__ */ new Map(), this.groups.set(n, e));
			let l = (c = e.get(t)) != null ? c : 0;
			e.set(t, l + 1);
			let o = Array.from(e.keys()).indexOf(t);
			function i() {
				let u = e.get(t);
				u > 1 ? e.set(t, u - 1) : e.delete(t);
			}
			return [o, i];
		}
	};
}
function C$1({ children: n }) {
	let t = import_react.useRef(a());
	return import_react.createElement(s.Provider, { value: t }, n);
}
function d(n) {
	let t = import_react.useContext(s);
	if (!t) throw new Error("You must wrap your component in a <StableCollection>");
	let e = f(), [l, o] = t.current.get(n, e);
	return import_react.useEffect(() => o, []), l;
}
function f() {
	var l, o, i;
	let n = (i = (o = (l = import_react.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED) == null ? void 0 : l.ReactCurrentOwner) == null ? void 0 : o.current) != null ? i : null;
	if (!n) return Symbol();
	let t = [], e = n;
	for (; e;) t.push(e.index), e = e.return;
	return "$." + t.join(".");
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/tabs/tabs.js
var ue$1 = ((t) => (t[t.Forwards = 0] = "Forwards", t[t.Backwards = 1] = "Backwards", t))(ue$1 || {}), Te = ((l) => (l[l.Less = -1] = "Less", l[l.Equal = 0] = "Equal", l[l.Greater = 1] = "Greater", l))(Te || {}), de$1 = ((a) => (a[a.SetSelectedIndex = 0] = "SetSelectedIndex", a[a.RegisterTab = 1] = "RegisterTab", a[a.UnregisterTab = 2] = "UnregisterTab", a[a.RegisterPanel = 3] = "RegisterPanel", a[a.UnregisterPanel = 4] = "UnregisterPanel", a))(de$1 || {});
var ce = {
	[0](e, n) {
		var i;
		let t = I$8(e.tabs, (c) => c.current), l = I$8(e.panels, (c) => c.current), o = t.filter((c) => {
			var p;
			return !((p = c.current) != null && p.hasAttribute("disabled"));
		}), a = {
			...e,
			tabs: t,
			panels: l
		};
		if (n.index < 0 || n.index > t.length - 1) {
			let c = u$11(Math.sign(n.index - e.selectedIndex), {
				[-1]: () => 1,
				[0]: () => u$11(Math.sign(n.index), {
					[-1]: () => 0,
					[0]: () => 0,
					[1]: () => 1
				}),
				[1]: () => 0
			});
			if (o.length === 0) return a;
			let p = u$11(c, {
				[0]: () => t.indexOf(o[0]),
				[1]: () => t.indexOf(o[o.length - 1])
			});
			return {
				...a,
				selectedIndex: p === -1 ? e.selectedIndex : p
			};
		}
		let T = t.slice(0, n.index), m = [...t.slice(n.index), ...T].find((c) => o.includes(c));
		if (!m) return a;
		let b = (i = t.indexOf(m)) != null ? i : e.selectedIndex;
		return b === -1 && (b = e.selectedIndex), {
			...a,
			selectedIndex: b
		};
	},
	[1](e, n) {
		if (e.tabs.includes(n.tab)) return e;
		let t = e.tabs[e.selectedIndex], l = I$8([...e.tabs, n.tab], (a) => a.current), o = e.selectedIndex;
		return e.info.current.isControlled || (o = l.indexOf(t), o === -1 && (o = e.selectedIndex)), {
			...e,
			tabs: l,
			selectedIndex: o
		};
	},
	[2](e, n) {
		return {
			...e,
			tabs: e.tabs.filter((t) => t !== n.tab)
		};
	},
	[3](e, n) {
		return e.panels.includes(n.panel) ? e : {
			...e,
			panels: I$8([...e.panels, n.panel], (t) => t.current)
		};
	},
	[4](e, n) {
		return {
			...e,
			panels: e.panels.filter((t) => t !== n.panel)
		};
	}
}, X$1 = (0, import_react.createContext)(null);
X$1.displayName = "TabsDataContext";
function F$1(e) {
	let n = (0, import_react.useContext)(X$1);
	if (n === null) {
		let t = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Tab.Group /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(t, F$1), t;
	}
	return n;
}
var $$1 = (0, import_react.createContext)(null);
$$1.displayName = "TabsActionsContext";
function q$1(e) {
	let n = (0, import_react.useContext)($$1);
	if (n === null) {
		let t = /* @__PURE__ */ new Error(`<${e} /> is missing a parent <Tab.Group /> component.`);
		throw Error.captureStackTrace && Error.captureStackTrace(t, q$1), t;
	}
	return n;
}
function fe(e, n) {
	return u$11(n.type, ce, e, n);
}
var be = import_react.Fragment;
function me(e, n) {
	let { defaultIndex: t = 0, vertical: l = !1, manual: o = !1, onChange: a, selectedIndex: T = null, ...R } = e;
	const m = l ? "vertical" : "horizontal", b = o ? "manual" : "auto";
	let i = T !== null, c = s$13({ isControlled: i }), p = y$3(n), [u, f] = (0, import_react.useReducer)(fe, {
		info: c,
		selectedIndex: T != null ? T : t,
		tabs: [],
		panels: []
	}), P = (0, import_react.useMemo)(() => ({ selectedIndex: u.selectedIndex }), [u.selectedIndex]), g = s$13(a || (() => {})), E = s$13(u.tabs), L = (0, import_react.useMemo)(() => ({
		orientation: m,
		activation: b,
		...u
	}), [
		m,
		b,
		u
	]), A = o$10((s) => (f({
		type: 1,
		tab: s
	}), () => f({
		type: 2,
		tab: s
	}))), S = o$10((s) => (f({
		type: 3,
		panel: s
	}), () => f({
		type: 4,
		panel: s
	}))), k = o$10((s) => {
		h.current !== s && g.current(s), i || f({
			type: 0,
			index: s
		});
	}), h = s$13(i ? e.selectedIndex : u.selectedIndex), W = (0, import_react.useMemo)(() => ({
		registerTab: A,
		registerPanel: S,
		change: k
	}), []);
	l$10(() => {
		f({
			type: 0,
			index: T != null ? T : t
		});
	}, [T]), l$10(() => {
		if (h.current === void 0 || u.tabs.length <= 0) return;
		let s = I$8(u.tabs, (d) => d.current);
		s.some((d, M) => u.tabs[M] !== d) && k(s.indexOf(u.tabs[h.current]));
	});
	let O = { ref: p };
	return import_react.createElement(C$1, null, import_react.createElement($$1.Provider, { value: W }, import_react.createElement(X$1.Provider, { value: L }, L.tabs.length <= 0 && import_react.createElement(b$1, { onFocus: () => {
		var s, r;
		for (let d of E.current) if (((s = d.current) == null ? void 0 : s.tabIndex) === 0) return (r = d.current) == null || r.focus(), !0;
		return !1;
	} }), C$5({
		ourProps: O,
		theirProps: R,
		slot: P,
		defaultTag: be,
		name: "Tabs"
	}))));
}
var Pe$1 = "div";
function ye$1(e, n) {
	let { orientation: t, selectedIndex: l } = F$1("Tab.List");
	return C$5({
		ourProps: {
			ref: y$3(n),
			role: "tablist",
			"aria-orientation": t
		},
		theirProps: e,
		slot: { selectedIndex: l },
		defaultTag: Pe$1,
		name: "Tabs.List"
	});
}
var xe$1 = "button";
function ge(e, n) {
	var O, s;
	let t = I$9(), { id: l = `headlessui-tabs-tab-${t}`, ...o } = e, { orientation: a, activation: T, selectedIndex: R, tabs: m, panels: b } = F$1("Tab"), i = q$1("Tab"), c = F$1("Tab"), p = (0, import_react.useRef)(null), u = y$3(p, n);
	l$10(() => i.registerTab(p), [i, p]);
	let f = d("tabs"), P = m.indexOf(p);
	P === -1 && (P = f);
	let g = P === R, E = o$10((r) => {
		var M;
		let d = r();
		if (d === N$5.Success && T === "auto") {
			let K = (M = o$5(p)) == null ? void 0 : M.activeElement, z = c.tabs.findIndex((te) => te.current === K);
			z !== -1 && i.change(z);
		}
		return d;
	}), L = o$10((r) => {
		let d = m.map((K) => K.current).filter(Boolean);
		if (r.key === o$1.Space || r.key === o$1.Enter) {
			r.preventDefault(), r.stopPropagation(), i.change(P);
			return;
		}
		switch (r.key) {
			case o$1.Home:
			case o$1.PageUp: return r.preventDefault(), r.stopPropagation(), E(() => O$2(d, M$5.First));
			case o$1.End:
			case o$1.PageDown: return r.preventDefault(), r.stopPropagation(), E(() => O$2(d, M$5.Last));
		}
		if (E(() => u$11(a, {
			vertical() {
				return r.key === o$1.ArrowUp ? O$2(d, M$5.Previous | M$5.WrapAround) : r.key === o$1.ArrowDown ? O$2(d, M$5.Next | M$5.WrapAround) : N$5.Error;
			},
			horizontal() {
				return r.key === o$1.ArrowLeft ? O$2(d, M$5.Previous | M$5.WrapAround) : r.key === o$1.ArrowRight ? O$2(d, M$5.Next | M$5.WrapAround) : N$5.Error;
			}
		})) === N$5.Success) return r.preventDefault();
	}), A = (0, import_react.useRef)(!1), S = o$10(() => {
		var r;
		A.current || (A.current = !0, (r = p.current) == null || r.focus({ preventScroll: !0 }), i.change(P), t$13(() => {
			A.current = !1;
		}));
	}), k = o$10((r) => {
		r.preventDefault();
	}), h = (0, import_react.useMemo)(() => {
		var r;
		return {
			selected: g,
			disabled: (r = e.disabled) != null ? r : !1
		};
	}, [g, e.disabled]);
	return C$5({
		ourProps: {
			ref: u,
			onKeyDown: L,
			onMouseDown: k,
			onClick: S,
			id: l,
			role: "tab",
			type: T$3(e, p),
			"aria-controls": (s = (O = b[P]) == null ? void 0 : O.current) == null ? void 0 : s.id,
			"aria-selected": g,
			tabIndex: g ? 0 : -1
		},
		theirProps: o,
		slot: h,
		defaultTag: xe$1,
		name: "Tabs.Tab"
	});
}
var Ee = "div";
function Ae$1(e, n) {
	let { selectedIndex: t } = F$1("Tab.Panels"), l = y$3(n), o = (0, import_react.useMemo)(() => ({ selectedIndex: t }), [t]);
	return C$5({
		ourProps: { ref: l },
		theirProps: e,
		slot: o,
		defaultTag: Ee,
		name: "Tabs.Panels"
	});
}
var Re$1 = "div", Le$1 = O$1.RenderStrategy | O$1.Static;
function _e$2(e, n) {
	var E, L, A, S;
	let t = I$9(), { id: l = `headlessui-tabs-panel-${t}`, tabIndex: o = 0, ...a } = e, { selectedIndex: T, tabs: R, panels: m } = F$1("Tab.Panel"), b = q$1("Tab.Panel"), i = (0, import_react.useRef)(null), c = y$3(i, n);
	l$10(() => b.registerPanel(i), [
		b,
		i,
		l
	]);
	let p = d("panels"), u = m.indexOf(i);
	u === -1 && (u = p);
	let f = u === T, P = (0, import_react.useMemo)(() => ({ selected: f }), [f]), g = {
		ref: c,
		id: l,
		role: "tabpanel",
		"aria-labelledby": (L = (E = R[u]) == null ? void 0 : E.current) == null ? void 0 : L.id,
		tabIndex: f ? o : -1
	};
	return !f && ((A = a.unmount) == null || A) && !((S = a.static) != null && S) ? import_react.createElement(u$8, {
		as: "span",
		"aria-hidden": "true",
		...g
	}) : C$5({
		ourProps: g,
		theirProps: a,
		slot: P,
		defaultTag: Re$1,
		features: Le$1,
		visible: f,
		name: "Tabs.Panel"
	});
}
var Se$1 = U$5(ge), Ie = U$5(me), De$1 = U$5(ye$1), Fe$1 = U$5(Ae$1), he = U$5(_e$2), $e = Object.assign(Se$1, {
	Group: Ie,
	List: De$1,
	Panels: Fe$1,
	Panel: he
});
//#endregion
//#region node_modules/@headlessui/react/dist/utils/once.js
function l(r) {
	let e = { called: !1 };
	return (...t) => {
		if (!e.called) return e.called = !0, r(...t);
	};
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/transitions/utils/transition.js
function g(t, ...e) {
	t && e.length > 0 && t.classList.add(...e);
}
function v(t, ...e) {
	t && e.length > 0 && t.classList.remove(...e);
}
function b(t, e) {
	let n = o$8();
	if (!t) return n.dispose;
	let { transitionDuration: m, transitionDelay: a } = getComputedStyle(t), [u, p] = [m, a].map((l) => {
		let [r = 0] = l.split(",").filter(Boolean).map((i) => i.includes("ms") ? parseFloat(i) : parseFloat(i) * 1e3).sort((i, T) => T - i);
		return r;
	}), o = u + p;
	if (o !== 0) {
		n.group((r) => {
			r.setTimeout(() => {
				e(), r.dispose();
			}, o), r.addEventListener(t, "transitionrun", (i) => {
				i.target === i.currentTarget && r.dispose();
			});
		});
		let l = n.addEventListener(t, "transitionend", (r) => {
			r.target === r.currentTarget && (e(), l());
		});
	} else e();
	return n.add(() => e()), n.dispose;
}
function M$1(t, e, n, m) {
	let a = n ? "enter" : "leave", u = o$8(), p = m !== void 0 ? l(m) : () => {};
	a === "enter" && (t.removeAttribute("hidden"), t.style.display = "");
	let o = u$11(a, {
		enter: () => e.enter,
		leave: () => e.leave
	}), l$11 = u$11(a, {
		enter: () => e.enterTo,
		leave: () => e.leaveTo
	}), r = u$11(a, {
		enter: () => e.enterFrom,
		leave: () => e.leaveFrom
	});
	return v(t, ...e.base, ...e.enter, ...e.enterTo, ...e.enterFrom, ...e.leave, ...e.leaveFrom, ...e.leaveTo, ...e.entered), g(t, ...e.base, ...o, ...r), u.nextFrame(() => {
		v(t, ...e.base, ...o, ...r), g(t, ...e.base, ...o, ...l$11), b(t, () => (v(t, ...e.base, ...o), g(t, ...e.base, ...e.entered), p()));
	}), u.dispose;
}
//#endregion
//#region node_modules/@headlessui/react/dist/hooks/use-transition.js
function D({ immediate: t, container: s, direction: n, classes: u, onStart: a, onStop: c }) {
	let l = f$6(), d = p$5(), e = s$13(n);
	l$10(() => {
		t && (e.current = "enter");
	}, [t]), l$10(() => {
		let r = o$8();
		d.add(r.dispose);
		let i = s.current;
		if (i && e.current !== "idle" && l.current) return r.dispose(), a.current(e.current), r.add(M$1(i, u.current, e.current === "enter", () => {
			r.dispose(), c.current(e.current);
		})), r.dispose;
	}, [n]);
}
//#endregion
//#region node_modules/@headlessui/react/dist/components/transitions/transition.js
function S(t = "") {
	return t.split(/\s+/).filter((n) => n.length > 1);
}
var I = (0, import_react.createContext)(null);
I.displayName = "TransitionContext";
var Se = ((r) => (r.Visible = "visible", r.Hidden = "hidden", r))(Se || {});
function ye() {
	let t = (0, import_react.useContext)(I);
	if (t === null) throw new Error("A <Transition.Child /> is used but it is missing a parent <Transition /> or <Transition.Root />.");
	return t;
}
function xe() {
	let t = (0, import_react.useContext)(M);
	if (t === null) throw new Error("A <Transition.Child /> is used but it is missing a parent <Transition /> or <Transition.Root />.");
	return t;
}
var M = (0, import_react.createContext)(null);
M.displayName = "NestingContext";
function U(t) {
	return "children" in t ? U(t.children) : t.current.filter(({ el: n }) => n.current !== null).filter(({ state: n }) => n === "visible").length > 0;
}
function se(t, n) {
	let r = s$13(t), s = (0, import_react.useRef)([]), R = f$6(), D = p$5(), p = o$10((i, e = v$4.Hidden) => {
		let a = s.current.findIndex(({ el: o }) => o === i);
		a !== -1 && (u$11(e, {
			[v$4.Unmount]() {
				s.current.splice(a, 1);
			},
			[v$4.Hidden]() {
				s.current[a].state = "hidden";
			}
		}), D.microTask(() => {
			var o;
			!U(s) && R.current && ((o = r.current) == null || o.call(r));
		}));
	}), x = o$10((i) => {
		let e = s.current.find(({ el: a }) => a === i);
		return e ? e.state !== "visible" && (e.state = "visible") : s.current.push({
			el: i,
			state: "visible"
		}), () => p(i, v$4.Unmount);
	}), h = (0, import_react.useRef)([]), v = (0, import_react.useRef)(Promise.resolve()), u = (0, import_react.useRef)({
		enter: [],
		leave: [],
		idle: []
	}), g = o$10((i, e, a) => {
		h.current.splice(0), n && (n.chains.current[e] = n.chains.current[e].filter(([o]) => o !== i)), n?.chains.current[e].push([i, new Promise((o) => {
			h.current.push(o);
		})]), n?.chains.current[e].push([i, new Promise((o) => {
			Promise.all(u.current[e].map(([f, N]) => N)).then(() => o());
		})]), e === "enter" ? v.current = v.current.then(() => n == null ? void 0 : n.wait.current).then(() => a(e)) : a(e);
	}), d = o$10((i, e, a) => {
		Promise.all(u.current[e].splice(0).map(([o, f]) => f)).then(() => {
			var o;
			(o = h.current.shift()) == null || o();
		}).then(() => a(e));
	});
	return (0, import_react.useMemo)(() => ({
		children: s,
		register: x,
		unregister: p,
		onStart: g,
		onStop: d,
		wait: v,
		chains: u
	}), [
		x,
		p,
		s,
		g,
		d,
		u,
		v
	]);
}
function Ne() {}
var Pe = [
	"beforeEnter",
	"afterEnter",
	"beforeLeave",
	"afterLeave"
];
function ae(t) {
	var r;
	let n = {};
	for (let s of Pe) n[s] = (r = t[s]) != null ? r : Ne;
	return n;
}
function Re(t) {
	let n = (0, import_react.useRef)(ae(t));
	return (0, import_react.useEffect)(() => {
		n.current = ae(t);
	}, [t]), n;
}
var De = "div", le = O$1.RenderStrategy;
function He(t, n) {
	var Q, Y;
	let { beforeEnter: r, afterEnter: s, beforeLeave: R, afterLeave: D$6, enter: p, enterFrom: x, enterTo: h, entered: v, leave: u, leaveFrom: g, leaveTo: d, ...i } = t, e = (0, import_react.useRef)(null), a = y$3(e, n), o = (Q = i.unmount) == null || Q ? v$4.Unmount : v$4.Hidden, { show: f, appear: N, initial: T } = ye(), [l, j] = (0, import_react.useState)(f ? "visible" : "hidden"), z = xe(), { register: L, unregister: O } = z;
	(0, import_react.useEffect)(() => L(e), [L, e]), (0, import_react.useEffect)(() => {
		if (o === v$4.Hidden && e.current) {
			if (f && l !== "visible") {
				j("visible");
				return;
			}
			return u$11(l, {
				["hidden"]: () => O(e),
				["visible"]: () => L(e)
			});
		}
	}, [
		l,
		e,
		L,
		O,
		f,
		o
	]);
	let k = s$13({
		base: S(i.className),
		enter: S(p),
		enterFrom: S(x),
		enterTo: S(h),
		entered: S(v),
		leave: S(u),
		leaveFrom: S(g),
		leaveTo: S(d)
	}), V = Re({
		beforeEnter: r,
		afterEnter: s,
		beforeLeave: R,
		afterLeave: D$6
	}), G = l$9();
	(0, import_react.useEffect)(() => {
		if (G && l === "visible" && e.current === null) throw new Error("Did you forget to passthrough the `ref` to the actual DOM node?");
	}, [
		e,
		l,
		G
	]);
	let Te = T && !N, K = N && f && T, de = (() => !G || Te ? "idle" : f ? "enter" : "leave")(), H = c$2(0), fe = o$10((C) => u$11(C, {
		enter: () => {
			H.addFlag(d$10.Opening), V.current.beforeEnter();
		},
		leave: () => {
			H.addFlag(d$10.Closing), V.current.beforeLeave();
		},
		idle: () => {}
	})), me = o$10((C) => u$11(C, {
		enter: () => {
			H.removeFlag(d$10.Opening), V.current.afterEnter();
		},
		leave: () => {
			H.removeFlag(d$10.Closing), V.current.afterLeave();
		},
		idle: () => {}
	})), w = se(() => {
		j("hidden"), O(e);
	}, z), B = (0, import_react.useRef)(!1);
	D({
		immediate: K,
		container: e,
		classes: k,
		direction: de,
		onStart: s$13((C) => {
			B.current = !0, w.onStart(e, C, fe);
		}),
		onStop: s$13((C) => {
			B.current = !1, w.onStop(e, C, me), C === "leave" && !U(w) && (j("hidden"), O(e));
		})
	});
	let P = i, ce = { ref: a };
	return K ? P = {
		...P,
		className: t$8(i.className, ...k.current.enter, ...k.current.enterFrom)
	} : B.current && (P.className = t$8(i.className, (Y = e.current) == null ? void 0 : Y.className), P.className === "" && delete P.className), import_react.createElement(M.Provider, { value: w }, import_react.createElement(s$6, { value: u$11(l, {
		["visible"]: d$10.Open,
		["hidden"]: d$10.Closed
	}) | H.flags }, C$5({
		ourProps: ce,
		theirProps: P,
		defaultTag: De,
		features: le,
		visible: l === "visible",
		name: "Transition.Child"
	})));
}
function Fe(t, n) {
	let { show: r, appear: s = !1, unmount: R = !0, ...D } = t, p = (0, import_react.useRef)(null), x = y$3(p, n);
	l$9();
	let h = u$7();
	if (r === void 0 && h !== null && (r = (h & d$10.Open) === d$10.Open), ![!0, !1].includes(r)) throw new Error("A <Transition /> is used but it is missing a `show={true | false}` prop.");
	let [v, u] = (0, import_react.useState)(r ? "visible" : "hidden"), g = se(() => {
		u("hidden");
	}), [d, i] = (0, import_react.useState)(!0), e = (0, import_react.useRef)([r]);
	l$10(() => {
		d !== !1 && e.current[e.current.length - 1] !== r && (e.current.push(r), i(!1));
	}, [e, r]);
	let a = (0, import_react.useMemo)(() => ({
		show: r,
		appear: s,
		initial: d
	}), [
		r,
		s,
		d
	]);
	(0, import_react.useEffect)(() => {
		if (r) u("visible");
		else if (!U(g)) u("hidden");
		else {
			let T = p.current;
			if (!T) return;
			let l = T.getBoundingClientRect();
			l.x === 0 && l.y === 0 && l.width === 0 && l.height === 0 && u("hidden");
		}
	}, [r, g]);
	let o = { unmount: R }, f = o$10(() => {
		var T;
		d && i(!1), (T = t.beforeEnter) == null || T.call(t);
	}), N = o$10(() => {
		var T;
		d && i(!1), (T = t.beforeLeave) == null || T.call(t);
	});
	return import_react.createElement(M.Provider, { value: g }, import_react.createElement(I.Provider, { value: a }, C$5({
		ourProps: {
			...o,
			as: import_react.Fragment,
			children: import_react.createElement(ue, {
				ref: x,
				...o,
				...D,
				beforeEnter: f,
				beforeLeave: N
			})
		},
		theirProps: {},
		defaultTag: import_react.Fragment,
		features: le,
		visible: v === "visible",
		name: "Transition"
	})));
}
function _e$1(t, n) {
	let r = (0, import_react.useContext)(I) !== null, s = u$7() !== null;
	return import_react.createElement(import_react.Fragment, null, !r && s ? import_react.createElement(q, {
		ref: n,
		...t
	}) : import_react.createElement(ue, {
		ref: n,
		...t
	}));
}
var q = U$5(Fe), ue = U$5(He), Le = U$5(_e$1), qe$1 = Object.assign(q, {
	Child: Le,
	Root: q
});
//#endregion
export { qt as Combobox, _t as Dialog, Ae as Disclosure, de as FocusTrap, It as Listbox, qe as Menu, Ct as Popover, te as Portal, it as RadioGroup, _e as Switch, $e as Tab, qe$1 as Transition };

//# sourceMappingURL=@headlessui_react.js.map