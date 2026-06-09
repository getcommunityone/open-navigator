import { n as __esmMin } from "./chunk-_TIqcEvS.js";
//#region node_modules/internmap/src/index.js
function intern_get({ _intern, _key }, value) {
	const key = _key(value);
	return _intern.has(key) ? _intern.get(key) : value;
}
function intern_set({ _intern, _key }, value) {
	const key = _key(value);
	if (_intern.has(key)) return _intern.get(key);
	_intern.set(key, value);
	return value;
}
function intern_delete({ _intern, _key }, value) {
	const key = _key(value);
	if (_intern.has(key)) {
		value = _intern.get(value);
		_intern.delete(key);
	}
	return value;
}
function keyof(value) {
	return value !== null && typeof value === "object" ? value.valueOf() : value;
}
var InternMap;
var init_src = __esmMin((() => {
	InternMap = class extends Map {
		constructor(entries, key = keyof) {
			super();
			Object.defineProperties(this, {
				_intern: { value: /* @__PURE__ */ new Map() },
				_key: { value: key }
			});
			if (entries != null) for (const [key, value] of entries) this.set(key, value);
		}
		get(key) {
			return super.get(intern_get(this, key));
		}
		has(key) {
			return super.has(intern_get(this, key));
		}
		set(key, value) {
			return super.set(intern_set(this, key), value);
		}
		delete(key) {
			return super.delete(intern_delete(this, key));
		}
	};
}));
//#endregion
export { init_src as n, InternMap as t };

//# sourceMappingURL=src-Cr0MutKw.js.map