import { a as __toESM } from "./chunk-_TIqcEvS.js";
import { t as require_react } from "./react.js";
import { t as require_react_dom } from "./react-dom-Dr7h9AAs.js";
//#region node_modules/@remix-run/router/dist/router.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_react_dom = /* @__PURE__ */ __toESM(require_react_dom());
/**
* @remix-run/router v1.23.3
*
* Copyright (c) Remix Software Inc.
*
* This source code is licensed under the MIT license found in the
* LICENSE.md file in the root directory of this source tree.
*
* @license MIT
*/
function _extends$2() {
	return _extends$2 = Object.assign ? Object.assign.bind() : function(n) {
		for (var e = 1; e < arguments.length; e++) {
			var t = arguments[e];
			for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
		}
		return n;
	}, _extends$2.apply(null, arguments);
}
/**
* Actions represent the type of change to a location value.
*/
var Action;
(function(Action) {
	/**
	* A POP indicates a change to an arbitrary index in the history stack, such
	* as a back or forward navigation. It does not describe the direction of the
	* navigation, only that the current index changed.
	*
	* Note: This is the default action for newly created history objects.
	*/
	Action["Pop"] = "POP";
	/**
	* A PUSH indicates a new entry being added to the history stack, such as when
	* a link is clicked and a new page loads. When this happens, all subsequent
	* entries in the stack are lost.
	*/
	Action["Push"] = "PUSH";
	/**
	* A REPLACE indicates the entry at the current index in the history stack
	* being replaced by a new one.
	*/
	Action["Replace"] = "REPLACE";
})(Action || (Action = {}));
var PopStateEventType = "popstate";
/**
* Memory history stores the current location in memory. It is designed for use
* in stateful non-browser environments like tests and React Native.
*/
function createMemoryHistory(options) {
	if (options === void 0) options = {};
	let { initialEntries = ["/"], initialIndex, v5Compat = false } = options;
	let entries;
	entries = initialEntries.map((entry, index) => createMemoryLocation(entry, typeof entry === "string" ? null : entry.state, index === 0 ? "default" : void 0));
	let index = clampIndex(initialIndex == null ? entries.length - 1 : initialIndex);
	let action = Action.Pop;
	let listener = null;
	function clampIndex(n) {
		return Math.min(Math.max(n, 0), entries.length - 1);
	}
	function getCurrentLocation() {
		return entries[index];
	}
	function createMemoryLocation(to, state, key) {
		if (state === void 0) state = null;
		let location = createLocation(entries ? getCurrentLocation().pathname : "/", to, state, key);
		warning(location.pathname.charAt(0) === "/", "relative pathnames are not supported in memory history: " + JSON.stringify(to));
		return location;
	}
	function createHref(to) {
		return typeof to === "string" ? to : createPath(to);
	}
	return {
		get index() {
			return index;
		},
		get action() {
			return action;
		},
		get location() {
			return getCurrentLocation();
		},
		createHref,
		createURL(to) {
			return new URL(createHref(to), "http://localhost");
		},
		encodeLocation(to) {
			let path = typeof to === "string" ? parsePath(to) : to;
			return {
				pathname: path.pathname || "",
				search: path.search || "",
				hash: path.hash || ""
			};
		},
		push(to, state) {
			action = Action.Push;
			let nextLocation = createMemoryLocation(to, state);
			index += 1;
			entries.splice(index, entries.length, nextLocation);
			if (v5Compat && listener) listener({
				action,
				location: nextLocation,
				delta: 1
			});
		},
		replace(to, state) {
			action = Action.Replace;
			let nextLocation = createMemoryLocation(to, state);
			entries[index] = nextLocation;
			if (v5Compat && listener) listener({
				action,
				location: nextLocation,
				delta: 0
			});
		},
		go(delta) {
			action = Action.Pop;
			let nextIndex = clampIndex(index + delta);
			let nextLocation = entries[nextIndex];
			index = nextIndex;
			if (listener) listener({
				action,
				location: nextLocation,
				delta
			});
		},
		listen(fn) {
			listener = fn;
			return () => {
				listener = null;
			};
		}
	};
}
/**
* Browser history stores the location in regular URLs. This is the standard for
* most web apps, but it requires some configuration on the server to ensure you
* serve the same app at multiple URLs.
*
* @see https://github.com/remix-run/history/tree/main/docs/api-reference.md#createbrowserhistory
*/
function createBrowserHistory(options) {
	if (options === void 0) options = {};
	function createBrowserLocation(window, globalHistory) {
		let { pathname, search, hash } = window.location;
		return createLocation("", {
			pathname,
			search,
			hash
		}, globalHistory.state && globalHistory.state.usr || null, globalHistory.state && globalHistory.state.key || "default");
	}
	function createBrowserHref(window, to) {
		return typeof to === "string" ? to : createPath(to);
	}
	return getUrlBasedHistory(createBrowserLocation, createBrowserHref, null, options);
}
/**
* Hash history stores the location in window.location.hash. This makes it ideal
* for situations where you don't want to send the location to the server for
* some reason, either because you do cannot configure it or the URL space is
* reserved for something else.
*
* @see https://github.com/remix-run/history/tree/main/docs/api-reference.md#createhashhistory
*/
function createHashHistory(options) {
	if (options === void 0) options = {};
	function createHashLocation(window, globalHistory) {
		let { pathname = "/", search = "", hash = "" } = parsePath(window.location.hash.substr(1));
		if (!pathname.startsWith("/") && !pathname.startsWith(".")) pathname = "/" + pathname;
		return createLocation("", {
			pathname,
			search,
			hash
		}, globalHistory.state && globalHistory.state.usr || null, globalHistory.state && globalHistory.state.key || "default");
	}
	function createHashHref(window, to) {
		let base = window.document.querySelector("base");
		let href = "";
		if (base && base.getAttribute("href")) {
			let url = window.location.href;
			let hashIndex = url.indexOf("#");
			href = hashIndex === -1 ? url : url.slice(0, hashIndex);
		}
		return href + "#" + (typeof to === "string" ? to : createPath(to));
	}
	function validateHashLocation(location, to) {
		warning(location.pathname.charAt(0) === "/", "relative pathnames are not supported in hash history.push(" + JSON.stringify(to) + ")");
	}
	return getUrlBasedHistory(createHashLocation, createHashHref, validateHashLocation, options);
}
function invariant(value, message) {
	if (value === false || value === null || typeof value === "undefined") throw new Error(message);
}
function warning(cond, message) {
	if (!cond) {
		if (typeof console !== "undefined") console.warn(message);
		try {
			throw new Error(message);
		} catch (e) {}
	}
}
function createKey() {
	return Math.random().toString(36).substr(2, 8);
}
/**
* For browser-based histories, we combine the state and key into an object
*/
function getHistoryState(location, index) {
	return {
		usr: location.state,
		key: location.key,
		idx: index
	};
}
/**
* Creates a Location object with a unique key from the given Path
*/
function createLocation(current, to, state, key) {
	if (state === void 0) state = null;
	return _extends$2({
		pathname: typeof current === "string" ? current : current.pathname,
		search: "",
		hash: ""
	}, typeof to === "string" ? parsePath(to) : to, {
		state,
		key: to && to.key || key || createKey()
	});
}
/**
* Creates a string URL path from the given pathname, search, and hash components.
*/
function createPath(_ref) {
	let { pathname = "/", search = "", hash = "" } = _ref;
	if (search && search !== "?") pathname += search.charAt(0) === "?" ? search : "?" + search;
	if (hash && hash !== "#") pathname += hash.charAt(0) === "#" ? hash : "#" + hash;
	return pathname;
}
/**
* Parses a string URL path into its separate pathname, search, and hash components.
*/
function parsePath(path) {
	let parsedPath = {};
	if (path) {
		let hashIndex = path.indexOf("#");
		if (hashIndex >= 0) {
			parsedPath.hash = path.substr(hashIndex);
			path = path.substr(0, hashIndex);
		}
		let searchIndex = path.indexOf("?");
		if (searchIndex >= 0) {
			parsedPath.search = path.substr(searchIndex);
			path = path.substr(0, searchIndex);
		}
		if (path) parsedPath.pathname = path;
	}
	return parsedPath;
}
function getUrlBasedHistory(getLocation, createHref, validateLocation, options) {
	if (options === void 0) options = {};
	let { window = document.defaultView, v5Compat = false } = options;
	let globalHistory = window.history;
	let action = Action.Pop;
	let listener = null;
	let index = getIndex();
	if (index == null) {
		index = 0;
		globalHistory.replaceState(_extends$2({}, globalHistory.state, { idx: index }), "");
	}
	function getIndex() {
		return (globalHistory.state || { idx: null }).idx;
	}
	function handlePop() {
		action = Action.Pop;
		let nextIndex = getIndex();
		let delta = nextIndex == null ? null : nextIndex - index;
		index = nextIndex;
		if (listener) listener({
			action,
			location: history.location,
			delta
		});
	}
	function push(to, state) {
		action = Action.Push;
		let location = createLocation(history.location, to, state);
		if (validateLocation) validateLocation(location, to);
		index = getIndex() + 1;
		let historyState = getHistoryState(location, index);
		let url = history.createHref(location);
		try {
			globalHistory.pushState(historyState, "", url);
		} catch (error) {
			if (error instanceof DOMException && error.name === "DataCloneError") throw error;
			window.location.assign(url);
		}
		if (v5Compat && listener) listener({
			action,
			location: history.location,
			delta: 1
		});
	}
	function replace(to, state) {
		action = Action.Replace;
		let location = createLocation(history.location, to, state);
		if (validateLocation) validateLocation(location, to);
		index = getIndex();
		let historyState = getHistoryState(location, index);
		let url = history.createHref(location);
		globalHistory.replaceState(historyState, "", url);
		if (v5Compat && listener) listener({
			action,
			location: history.location,
			delta: 0
		});
	}
	function createURL(to) {
		let base = window.location.origin !== "null" ? window.location.origin : window.location.href;
		let href = typeof to === "string" ? to : createPath(to);
		href = href.replace(/ $/, "%20");
		invariant(base, "No window.location.(origin|href) available to create URL for href: " + href);
		return new URL(href, base);
	}
	let history = {
		get action() {
			return action;
		},
		get location() {
			return getLocation(window, globalHistory);
		},
		listen(fn) {
			if (listener) throw new Error("A history only accepts one active listener");
			window.addEventListener(PopStateEventType, handlePop);
			listener = fn;
			return () => {
				window.removeEventListener(PopStateEventType, handlePop);
				listener = null;
			};
		},
		createHref(to) {
			return createHref(window, to);
		},
		createURL,
		encodeLocation(to) {
			let url = createURL(to);
			return {
				pathname: url.pathname,
				search: url.search,
				hash: url.hash
			};
		},
		push,
		replace,
		go(n) {
			return globalHistory.go(n);
		}
	};
	return history;
}
var ResultType;
(function(ResultType) {
	ResultType["data"] = "data";
	ResultType["deferred"] = "deferred";
	ResultType["redirect"] = "redirect";
	ResultType["error"] = "error";
})(ResultType || (ResultType = {}));
var immutableRouteKeys = new Set([
	"lazy",
	"caseSensitive",
	"path",
	"id",
	"index",
	"children"
]);
function isIndexRoute(route) {
	return route.index === true;
}
function convertRoutesToDataRoutes(routes, mapRouteProperties, parentPath, manifest) {
	if (parentPath === void 0) parentPath = [];
	if (manifest === void 0) manifest = {};
	return routes.map((route, index) => {
		let treePath = [...parentPath, String(index)];
		let id = typeof route.id === "string" ? route.id : treePath.join("-");
		invariant(route.index !== true || !route.children, "Cannot specify children on an index route");
		invariant(!manifest[id], "Found a route id collision on id \"" + id + "\".  Route id's must be globally unique within Data Router usages");
		if (isIndexRoute(route)) {
			let indexRoute = _extends$2({}, route, mapRouteProperties(route), { id });
			manifest[id] = indexRoute;
			return indexRoute;
		} else {
			let pathOrLayoutRoute = _extends$2({}, route, mapRouteProperties(route), {
				id,
				children: void 0
			});
			manifest[id] = pathOrLayoutRoute;
			if (route.children) pathOrLayoutRoute.children = convertRoutesToDataRoutes(route.children, mapRouteProperties, treePath, manifest);
			return pathOrLayoutRoute;
		}
	});
}
/**
* Matches the given routes to a location and returns the match data.
*
* @see https://reactrouter.com/v6/utils/match-routes
*/
function matchRoutes(routes, locationArg, basename) {
	if (basename === void 0) basename = "/";
	return matchRoutesImpl(routes, locationArg, basename, false);
}
function matchRoutesImpl(routes, locationArg, basename, allowPartial) {
	let pathname = stripBasename((typeof locationArg === "string" ? parsePath(locationArg) : locationArg).pathname || "/", basename);
	if (pathname == null) return null;
	let branches = flattenRoutes(routes);
	rankRouteBranches(branches);
	let matches = null;
	let decoded = decodePath(pathname);
	for (let i = 0; matches == null && i < branches.length; ++i) matches = matchRouteBranch(branches[i], decoded, allowPartial);
	return matches;
}
function convertRouteMatchToUiMatch(match, loaderData) {
	let { route, pathname, params } = match;
	return {
		id: route.id,
		pathname,
		params,
		data: loaderData[route.id],
		handle: route.handle
	};
}
function flattenRoutes(routes, branches, parentsMeta, parentPath) {
	if (branches === void 0) branches = [];
	if (parentsMeta === void 0) parentsMeta = [];
	if (parentPath === void 0) parentPath = "";
	let flattenRoute = (route, index, relativePath) => {
		let meta = {
			relativePath: relativePath === void 0 ? route.path || "" : relativePath,
			caseSensitive: route.caseSensitive === true,
			childrenIndex: index,
			route
		};
		if (meta.relativePath.startsWith("/")) {
			invariant(meta.relativePath.startsWith(parentPath), "Absolute route path \"" + meta.relativePath + "\" nested under path " + ("\"" + parentPath + "\" is not valid. An absolute child route path ") + "must start with the combined path of all its parent routes.");
			meta.relativePath = meta.relativePath.slice(parentPath.length);
		}
		let path = joinPaths([parentPath, meta.relativePath]);
		let routesMeta = parentsMeta.concat(meta);
		if (route.children && route.children.length > 0) {
			invariant(route.index !== true, "Index routes must not have child routes. Please remove " + ("all child routes from route path \"" + path + "\"."));
			flattenRoutes(route.children, branches, routesMeta, path);
		}
		if (route.path == null && !route.index) return;
		branches.push({
			path,
			score: computeScore(path, route.index),
			routesMeta
		});
	};
	routes.forEach((route, index) => {
		var _route$path;
		if (route.path === "" || !((_route$path = route.path) != null && _route$path.includes("?"))) flattenRoute(route, index);
		else for (let exploded of explodeOptionalSegments(route.path)) flattenRoute(route, index, exploded);
	});
	return branches;
}
/**
* Computes all combinations of optional path segments for a given path,
* excluding combinations that are ambiguous and of lower priority.
*
* For example, `/one/:two?/three/:four?/:five?` explodes to:
* - `/one/three`
* - `/one/:two/three`
* - `/one/three/:four`
* - `/one/three/:five`
* - `/one/:two/three/:four`
* - `/one/:two/three/:five`
* - `/one/three/:four/:five`
* - `/one/:two/three/:four/:five`
*/
function explodeOptionalSegments(path) {
	let segments = path.split("/");
	if (segments.length === 0) return [];
	let [first, ...rest] = segments;
	let isOptional = first.endsWith("?");
	let required = first.replace(/\?$/, "");
	if (rest.length === 0) return isOptional ? [required, ""] : [required];
	let restExploded = explodeOptionalSegments(rest.join("/"));
	let result = [];
	result.push(...restExploded.map((subpath) => subpath === "" ? required : [required, subpath].join("/")));
	if (isOptional) result.push(...restExploded);
	return result.map((exploded) => path.startsWith("/") && exploded === "" ? "/" : exploded);
}
function rankRouteBranches(branches) {
	branches.sort((a, b) => a.score !== b.score ? b.score - a.score : compareIndexes(a.routesMeta.map((meta) => meta.childrenIndex), b.routesMeta.map((meta) => meta.childrenIndex)));
}
var paramRe = /^:[\w-]+$/;
var dynamicSegmentValue = 3;
var indexRouteValue = 2;
var emptySegmentValue = 1;
var staticSegmentValue = 10;
var splatPenalty = -2;
var isSplat = (s) => s === "*";
function computeScore(path, index) {
	let segments = path.split("/");
	let initialScore = segments.length;
	if (segments.some(isSplat)) initialScore += splatPenalty;
	if (index) initialScore += indexRouteValue;
	return segments.filter((s) => !isSplat(s)).reduce((score, segment) => score + (paramRe.test(segment) ? dynamicSegmentValue : segment === "" ? emptySegmentValue : staticSegmentValue), initialScore);
}
function compareIndexes(a, b) {
	return a.length === b.length && a.slice(0, -1).every((n, i) => n === b[i]) ? a[a.length - 1] - b[b.length - 1] : 0;
}
function matchRouteBranch(branch, pathname, allowPartial) {
	if (allowPartial === void 0) allowPartial = false;
	let { routesMeta } = branch;
	let matchedParams = {};
	let matchedPathname = "/";
	let matches = [];
	for (let i = 0; i < routesMeta.length; ++i) {
		let meta = routesMeta[i];
		let end = i === routesMeta.length - 1;
		let remainingPathname = matchedPathname === "/" ? pathname : pathname.slice(matchedPathname.length) || "/";
		let match = matchPath({
			path: meta.relativePath,
			caseSensitive: meta.caseSensitive,
			end
		}, remainingPathname);
		let route = meta.route;
		if (!match && end && allowPartial && !routesMeta[routesMeta.length - 1].route.index) match = matchPath({
			path: meta.relativePath,
			caseSensitive: meta.caseSensitive,
			end: false
		}, remainingPathname);
		if (!match) return null;
		Object.assign(matchedParams, match.params);
		matches.push({
			params: matchedParams,
			pathname: joinPaths([matchedPathname, match.pathname]),
			pathnameBase: normalizePathname(joinPaths([matchedPathname, match.pathnameBase])),
			route
		});
		if (match.pathnameBase !== "/") matchedPathname = joinPaths([matchedPathname, match.pathnameBase]);
	}
	return matches;
}
/**
* Returns a path with params interpolated.
*
* @see https://reactrouter.com/v6/utils/generate-path
*/
function generatePath(originalPath, params) {
	if (params === void 0) params = {};
	let path = originalPath;
	if (path.endsWith("*") && path !== "*" && !path.endsWith("/*")) {
		warning(false, "Route path \"" + path + "\" will be treated as if it were " + ("\"" + path.replace(/\*$/, "/*") + "\" because the `*` character must ") + "always follow a `/` in the pattern. To get rid of this warning, " + ("please change the route path to \"" + path.replace(/\*$/, "/*") + "\"."));
		path = path.replace(/\*$/, "/*");
	}
	const prefix = path.startsWith("/") ? "/" : "";
	const stringify = (p) => p == null ? "" : typeof p === "string" ? p : String(p);
	return prefix + path.split(/\/+/).map((segment, index, array) => {
		if (index === array.length - 1 && segment === "*") return stringify(params["*"]);
		const keyMatch = segment.match(/^:([\w-]+)(\??)$/);
		if (keyMatch) {
			const [, key, optional] = keyMatch;
			let param = params[key];
			invariant(optional === "?" || param != null, "Missing \":" + key + "\" param");
			return stringify(param);
		}
		return segment.replace(/\?$/g, "");
	}).filter((segment) => !!segment).join("/");
}
/**
* Performs pattern matching on a URL pathname and returns information about
* the match.
*
* @see https://reactrouter.com/v6/utils/match-path
*/
function matchPath(pattern, pathname) {
	if (typeof pattern === "string") pattern = {
		path: pattern,
		caseSensitive: false,
		end: true
	};
	let [matcher, compiledParams] = compilePath(pattern.path, pattern.caseSensitive, pattern.end);
	let match = pathname.match(matcher);
	if (!match) return null;
	let matchedPathname = match[0];
	let pathnameBase = matchedPathname.replace(/(.)\/+$/, "$1");
	let captureGroups = match.slice(1);
	return {
		params: compiledParams.reduce((memo, _ref, index) => {
			let { paramName, isOptional } = _ref;
			if (paramName === "*") {
				let splatValue = captureGroups[index] || "";
				pathnameBase = matchedPathname.slice(0, matchedPathname.length - splatValue.length).replace(/(.)\/+$/, "$1");
			}
			const value = captureGroups[index];
			if (isOptional && !value) memo[paramName] = void 0;
			else memo[paramName] = (value || "").replace(/%2F/g, "/");
			return memo;
		}, {}),
		pathname: matchedPathname,
		pathnameBase,
		pattern
	};
}
function compilePath(path, caseSensitive, end) {
	if (caseSensitive === void 0) caseSensitive = false;
	if (end === void 0) end = true;
	warning(path === "*" || !path.endsWith("*") || path.endsWith("/*"), "Route path \"" + path + "\" will be treated as if it were " + ("\"" + path.replace(/\*$/, "/*") + "\" because the `*` character must ") + "always follow a `/` in the pattern. To get rid of this warning, " + ("please change the route path to \"" + path.replace(/\*$/, "/*") + "\"."));
	let params = [];
	let regexpSource = "^" + path.replace(/\/*\*?$/, "").replace(/^\/*/, "/").replace(/[\\.*+^${}|()[\]]/g, "\\$&").replace(/\/:([\w-]+)(\?)?/g, (_, paramName, isOptional) => {
		params.push({
			paramName,
			isOptional: isOptional != null
		});
		return isOptional ? "/?([^\\/]+)?" : "/([^\\/]+)";
	});
	if (path.endsWith("*")) {
		params.push({ paramName: "*" });
		regexpSource += path === "*" || path === "/*" ? "(.*)$" : "(?:\\/(.+)|\\/*)$";
	} else if (end) regexpSource += "\\/*$";
	else if (path !== "" && path !== "/") regexpSource += "(?:(?=\\/|$))";
	return [new RegExp(regexpSource, caseSensitive ? void 0 : "i"), params];
}
function decodePath(value) {
	try {
		return value.split("/").map((v) => decodeURIComponent(v).replace(/\//g, "%2F")).join("/");
	} catch (error) {
		warning(false, "The URL path \"" + value + "\" could not be decoded because it is is a malformed URL segment. This is probably due to a bad percent " + ("encoding (" + error + ")."));
		return value;
	}
}
/**
* @private
*/
function stripBasename(pathname, basename) {
	if (basename === "/") return pathname;
	if (!pathname.toLowerCase().startsWith(basename.toLowerCase())) return null;
	let startIndex = basename.endsWith("/") ? basename.length - 1 : basename.length;
	let nextChar = pathname.charAt(startIndex);
	if (nextChar && nextChar !== "/") return null;
	return pathname.slice(startIndex) || "/";
}
var ABSOLUTE_URL_REGEX$1 = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;
var isAbsoluteUrl = (url) => ABSOLUTE_URL_REGEX$1.test(url);
/**
* Returns a resolved path object relative to the given pathname.
*
* @see https://reactrouter.com/v6/utils/resolve-path
*/
function resolvePath(to, fromPathname) {
	if (fromPathname === void 0) fromPathname = "/";
	let { pathname: toPathname, search = "", hash = "" } = typeof to === "string" ? parsePath(to) : to;
	let pathname;
	if (toPathname) if (isAbsoluteUrl(toPathname)) pathname = toPathname;
	else {
		if (toPathname.includes("//")) {
			let oldPathname = toPathname;
			toPathname = removeDoubleSlashes(toPathname);
			warning(false, "Pathnames cannot have embedded double slashes - normalizing " + (oldPathname + " -> " + toPathname));
		}
		if (toPathname.startsWith("/")) pathname = resolvePathname(toPathname.substring(1), "/");
		else pathname = resolvePathname(toPathname, fromPathname);
	}
	else pathname = fromPathname;
	return {
		pathname,
		search: normalizeSearch(search),
		hash: normalizeHash(hash)
	};
}
function resolvePathname(relativePath, fromPathname) {
	let segments = fromPathname.replace(/\/+$/, "").split("/");
	relativePath.split("/").forEach((segment) => {
		if (segment === "..") {
			if (segments.length > 1) segments.pop();
		} else if (segment !== ".") segments.push(segment);
	});
	return segments.length > 1 ? segments.join("/") : "/";
}
function getInvalidPathError(char, field, dest, path) {
	return "Cannot include a '" + char + "' character in a manually specified " + ("`to." + field + "` field [" + JSON.stringify(path) + "].  Please separate it out to the ") + ("`to." + dest + "` field. Alternatively you may provide the full path as ") + "a string in <Link to=\"...\"> and the router will parse it for you.";
}
/**
* @private
*
* When processing relative navigation we want to ignore ancestor routes that
* do not contribute to the path, such that index/pathless layout routes don't
* interfere.
*
* For example, when moving a route element into an index route and/or a
* pathless layout route, relative link behavior contained within should stay
* the same.  Both of the following examples should link back to the root:
*
*   <Route path="/">
*     <Route path="accounts" element={<Link to=".."}>
*   </Route>
*
*   <Route path="/">
*     <Route path="accounts">
*       <Route element={<AccountsLayout />}>       // <-- Does not contribute
*         <Route index element={<Link to=".."} />  // <-- Does not contribute
*       </Route
*     </Route>
*   </Route>
*/
function getPathContributingMatches(matches) {
	return matches.filter((match, index) => index === 0 || match.route.path && match.route.path.length > 0);
}
function getResolveToMatches(matches, v7_relativeSplatPath) {
	let pathMatches = getPathContributingMatches(matches);
	if (v7_relativeSplatPath) return pathMatches.map((match, idx) => idx === pathMatches.length - 1 ? match.pathname : match.pathnameBase);
	return pathMatches.map((match) => match.pathnameBase);
}
/**
* @private
*/
function resolveTo(toArg, routePathnames, locationPathname, isPathRelative) {
	if (isPathRelative === void 0) isPathRelative = false;
	let to;
	if (typeof toArg === "string") to = parsePath(toArg);
	else {
		to = _extends$2({}, toArg);
		invariant(!to.pathname || !to.pathname.includes("?"), getInvalidPathError("?", "pathname", "search", to));
		invariant(!to.pathname || !to.pathname.includes("#"), getInvalidPathError("#", "pathname", "hash", to));
		invariant(!to.search || !to.search.includes("#"), getInvalidPathError("#", "search", "hash", to));
	}
	let isEmptyPath = toArg === "" || to.pathname === "";
	let toPathname = isEmptyPath ? "/" : to.pathname;
	let from;
	if (toPathname == null) from = locationPathname;
	else {
		let routePathnameIndex = routePathnames.length - 1;
		if (!isPathRelative && toPathname.startsWith("..")) {
			let toSegments = toPathname.split("/");
			while (toSegments[0] === "..") {
				toSegments.shift();
				routePathnameIndex -= 1;
			}
			to.pathname = toSegments.join("/");
		}
		from = routePathnameIndex >= 0 ? routePathnames[routePathnameIndex] : "/";
	}
	let path = resolvePath(to, from);
	let hasExplicitTrailingSlash = toPathname && toPathname !== "/" && toPathname.endsWith("/");
	let hasCurrentTrailingSlash = (isEmptyPath || toPathname === ".") && locationPathname.endsWith("/");
	if (!path.pathname.endsWith("/") && (hasExplicitTrailingSlash || hasCurrentTrailingSlash)) path.pathname += "/";
	return path;
}
var removeDoubleSlashes = (path) => path.replace(/\/\/+/g, "/");
/**
* @private
*/
var joinPaths = (paths) => removeDoubleSlashes(paths.join("/"));
/**
* @private
*/
var normalizePathname = (pathname) => pathname.replace(/\/+$/, "").replace(/^\/*/, "/");
/**
* @private
*/
var normalizeSearch = (search) => !search || search === "?" ? "" : search.startsWith("?") ? search : "?" + search;
/**
* @private
*/
var normalizeHash = (hash) => !hash || hash === "#" ? "" : hash.startsWith("#") ? hash : "#" + hash;
/**
* This is a shortcut for creating `application/json` responses. Converts `data`
* to JSON and sets the `Content-Type` header.
*
* @deprecated The `json` method is deprecated in favor of returning raw objects.
* This method will be removed in v7.
*/
var json = function json(data, init) {
	if (init === void 0) init = {};
	let responseInit = typeof init === "number" ? { status: init } : init;
	let headers = new Headers(responseInit.headers);
	if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json; charset=utf-8");
	return new Response(JSON.stringify(data), _extends$2({}, responseInit, { headers }));
};
var AbortedDeferredError = class extends Error {};
var DeferredData = class {
	constructor(data, responseInit) {
		this.pendingKeysSet = /* @__PURE__ */ new Set();
		this.subscribers = /* @__PURE__ */ new Set();
		this.deferredKeys = [];
		invariant(data && typeof data === "object" && !Array.isArray(data), "defer() only accepts plain objects");
		let reject;
		this.abortPromise = new Promise((_, r) => reject = r);
		this.controller = new AbortController();
		let onAbort = () => reject(new AbortedDeferredError("Deferred data aborted"));
		this.unlistenAbortSignal = () => this.controller.signal.removeEventListener("abort", onAbort);
		this.controller.signal.addEventListener("abort", onAbort);
		this.data = Object.entries(data).reduce((acc, _ref2) => {
			let [key, value] = _ref2;
			return Object.assign(acc, { [key]: this.trackPromise(key, value) });
		}, {});
		if (this.done) this.unlistenAbortSignal();
		this.init = responseInit;
	}
	trackPromise(key, value) {
		if (!(value instanceof Promise)) return value;
		this.deferredKeys.push(key);
		this.pendingKeysSet.add(key);
		let promise = Promise.race([value, this.abortPromise]).then((data) => this.onSettle(promise, key, void 0, data), (error) => this.onSettle(promise, key, error));
		promise.catch(() => {});
		Object.defineProperty(promise, "_tracked", { get: () => true });
		return promise;
	}
	onSettle(promise, key, error, data) {
		if (this.controller.signal.aborted && error instanceof AbortedDeferredError) {
			this.unlistenAbortSignal();
			Object.defineProperty(promise, "_error", { get: () => error });
			return Promise.reject(error);
		}
		this.pendingKeysSet.delete(key);
		if (this.done) this.unlistenAbortSignal();
		if (error === void 0 && data === void 0) {
			let undefinedError = /* @__PURE__ */ new Error("Deferred data for key \"" + key + "\" resolved/rejected with `undefined`, you must resolve/reject with a value or `null`.");
			Object.defineProperty(promise, "_error", { get: () => undefinedError });
			this.emit(false, key);
			return Promise.reject(undefinedError);
		}
		if (data === void 0) {
			Object.defineProperty(promise, "_error", { get: () => error });
			this.emit(false, key);
			return Promise.reject(error);
		}
		Object.defineProperty(promise, "_data", { get: () => data });
		this.emit(false, key);
		return data;
	}
	emit(aborted, settledKey) {
		this.subscribers.forEach((subscriber) => subscriber(aborted, settledKey));
	}
	subscribe(fn) {
		this.subscribers.add(fn);
		return () => this.subscribers.delete(fn);
	}
	cancel() {
		this.controller.abort();
		this.pendingKeysSet.forEach((v, k) => this.pendingKeysSet.delete(k));
		this.emit(true);
	}
	async resolveData(signal) {
		let aborted = false;
		if (!this.done) {
			let onAbort = () => this.cancel();
			signal.addEventListener("abort", onAbort);
			aborted = await new Promise((resolve) => {
				this.subscribe((aborted) => {
					signal.removeEventListener("abort", onAbort);
					if (aborted || this.done) resolve(aborted);
				});
			});
		}
		return aborted;
	}
	get done() {
		return this.pendingKeysSet.size === 0;
	}
	get unwrappedData() {
		invariant(this.data !== null && this.done, "Can only unwrap data on initialized and settled deferreds");
		return Object.entries(this.data).reduce((acc, _ref3) => {
			let [key, value] = _ref3;
			return Object.assign(acc, { [key]: unwrapTrackedPromise(value) });
		}, {});
	}
	get pendingKeys() {
		return Array.from(this.pendingKeysSet);
	}
};
function isTrackedPromise(value) {
	return value instanceof Promise && value._tracked === true;
}
function unwrapTrackedPromise(value) {
	if (!isTrackedPromise(value)) return value;
	if (value._error) throw value._error;
	return value._data;
}
/**
* @deprecated The `defer` method is deprecated in favor of returning raw
* objects. This method will be removed in v7.
*/
var defer = function defer(data, init) {
	if (init === void 0) init = {};
	return new DeferredData(data, typeof init === "number" ? { status: init } : init);
};
/**
* A redirect response. Sets the status code and the `Location` header.
* Defaults to "302 Found".
*/
var redirect = function redirect(url, init) {
	if (init === void 0) init = 302;
	let responseInit = init;
	if (typeof responseInit === "number") responseInit = { status: responseInit };
	else if (typeof responseInit.status === "undefined") responseInit.status = 302;
	let headers = new Headers(responseInit.headers);
	headers.set("Location", url);
	return new Response(null, _extends$2({}, responseInit, { headers }));
};
/**
* A redirect response that will force a document reload to the new location.
* Sets the status code and the `Location` header.
* Defaults to "302 Found".
*/
var redirectDocument = (url, init) => {
	let response = redirect(url, init);
	response.headers.set("X-Remix-Reload-Document", "true");
	return response;
};
/**
* A redirect response that will perform a `history.replaceState` instead of a
* `history.pushState` for client-side navigation redirects.
* Sets the status code and the `Location` header.
* Defaults to "302 Found".
*/
var replace = (url, init) => {
	let response = redirect(url, init);
	response.headers.set("X-Remix-Replace", "true");
	return response;
};
/**
* @private
* Utility class we use to hold auto-unwrapped 4xx/5xx Response bodies
*
* We don't export the class for public use since it's an implementation
* detail, but we export the interface above so folks can build their own
* abstractions around instances via isRouteErrorResponse()
*/
var ErrorResponseImpl = class {
	constructor(status, statusText, data, internal) {
		if (internal === void 0) internal = false;
		this.status = status;
		this.statusText = statusText || "";
		this.internal = internal;
		if (data instanceof Error) {
			this.data = data.toString();
			this.error = data;
		} else this.data = data;
	}
};
/**
* Check if the given error is an ErrorResponse generated from a 4xx/5xx
* Response thrown from an action/loader
*/
function isRouteErrorResponse(error) {
	return error != null && typeof error.status === "number" && typeof error.statusText === "string" && typeof error.internal === "boolean" && "data" in error;
}
var validMutationMethodsArr = [
	"post",
	"put",
	"patch",
	"delete"
];
var validMutationMethods = new Set(validMutationMethodsArr);
var validRequestMethodsArr = ["get", ...validMutationMethodsArr];
var validRequestMethods = new Set(validRequestMethodsArr);
var redirectStatusCodes = new Set([
	301,
	302,
	303,
	307,
	308
]);
var redirectPreserveMethodStatusCodes = new Set([307, 308]);
var IDLE_NAVIGATION = {
	state: "idle",
	location: void 0,
	formMethod: void 0,
	formAction: void 0,
	formEncType: void 0,
	formData: void 0,
	json: void 0,
	text: void 0
};
var IDLE_FETCHER = {
	state: "idle",
	data: void 0,
	formMethod: void 0,
	formAction: void 0,
	formEncType: void 0,
	formData: void 0,
	json: void 0,
	text: void 0
};
var IDLE_BLOCKER = {
	state: "unblocked",
	proceed: void 0,
	reset: void 0,
	location: void 0
};
var ABSOLUTE_URL_REGEX$2 = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;
var defaultMapRouteProperties = (route) => ({ hasErrorBoundary: Boolean(route.hasErrorBoundary) });
var TRANSITIONS_STORAGE_KEY = "remix-router-transitions";
/**
* Create a router and listen to history POP navigations
*/
function createRouter(init) {
	const routerWindow = init.window ? init.window : typeof window !== "undefined" ? window : void 0;
	const isBrowser = typeof routerWindow !== "undefined" && typeof routerWindow.document !== "undefined" && typeof routerWindow.document.createElement !== "undefined";
	const isServer = !isBrowser;
	invariant(init.routes.length > 0, "You must provide a non-empty routes array to createRouter");
	let mapRouteProperties;
	if (init.mapRouteProperties) mapRouteProperties = init.mapRouteProperties;
	else if (init.detectErrorBoundary) {
		let detectErrorBoundary = init.detectErrorBoundary;
		mapRouteProperties = (route) => ({ hasErrorBoundary: detectErrorBoundary(route) });
	} else mapRouteProperties = defaultMapRouteProperties;
	let manifest = {};
	let dataRoutes = convertRoutesToDataRoutes(init.routes, mapRouteProperties, void 0, manifest);
	let inFlightDataRoutes;
	let basename = init.basename || "/";
	let dataStrategyImpl = init.dataStrategy || defaultDataStrategy;
	let patchRoutesOnNavigationImpl = init.patchRoutesOnNavigation;
	let future = _extends$2({
		v7_fetcherPersist: false,
		v7_normalizeFormMethod: false,
		v7_partialHydration: false,
		v7_prependBasename: false,
		v7_relativeSplatPath: false,
		v7_skipActionErrorRevalidation: false
	}, init.future);
	let unlistenHistory = null;
	let subscribers = /* @__PURE__ */ new Set();
	let savedScrollPositions = null;
	let getScrollRestorationKey = null;
	let getScrollPosition = null;
	let initialScrollRestored = init.hydrationData != null;
	let initialMatches = matchRoutes(dataRoutes, init.history.location, basename);
	let initialMatchesIsFOW = false;
	let initialErrors = null;
	if (initialMatches == null && !patchRoutesOnNavigationImpl) {
		let error = getInternalRouterError(404, { pathname: init.history.location.pathname });
		let { matches, route } = getShortCircuitMatches(dataRoutes);
		initialMatches = matches;
		initialErrors = { [route.id]: error };
	}
	if (initialMatches && !init.hydrationData) {
		if (checkFogOfWar(initialMatches, dataRoutes, init.history.location.pathname).active) initialMatches = null;
	}
	let initialized;
	if (!initialMatches) {
		initialized = false;
		initialMatches = [];
		if (future.v7_partialHydration) {
			let fogOfWar = checkFogOfWar(null, dataRoutes, init.history.location.pathname);
			if (fogOfWar.active && fogOfWar.matches) {
				initialMatchesIsFOW = true;
				initialMatches = fogOfWar.matches;
			}
		}
	} else if (initialMatches.some((m) => m.route.lazy)) initialized = false;
	else if (!initialMatches.some((m) => m.route.loader)) initialized = true;
	else if (future.v7_partialHydration) {
		let loaderData = init.hydrationData ? init.hydrationData.loaderData : null;
		let errors = init.hydrationData ? init.hydrationData.errors : null;
		if (errors) {
			let idx = initialMatches.findIndex((m) => errors[m.route.id] !== void 0);
			initialized = initialMatches.slice(0, idx + 1).every((m) => !shouldLoadRouteOnHydration(m.route, loaderData, errors));
		} else initialized = initialMatches.every((m) => !shouldLoadRouteOnHydration(m.route, loaderData, errors));
	} else initialized = init.hydrationData != null;
	let router;
	let state = {
		historyAction: init.history.action,
		location: init.history.location,
		matches: initialMatches,
		initialized,
		navigation: IDLE_NAVIGATION,
		restoreScrollPosition: init.hydrationData != null ? false : null,
		preventScrollReset: false,
		revalidation: "idle",
		loaderData: init.hydrationData && init.hydrationData.loaderData || {},
		actionData: init.hydrationData && init.hydrationData.actionData || null,
		errors: init.hydrationData && init.hydrationData.errors || initialErrors,
		fetchers: /* @__PURE__ */ new Map(),
		blockers: /* @__PURE__ */ new Map()
	};
	let pendingAction = Action.Pop;
	let pendingPreventScrollReset = false;
	let pendingNavigationController;
	let pendingViewTransitionEnabled = false;
	let appliedViewTransitions = /* @__PURE__ */ new Map();
	let removePageHideEventListener = null;
	let isUninterruptedRevalidation = false;
	let isRevalidationRequired = false;
	let cancelledDeferredRoutes = [];
	let cancelledFetcherLoads = /* @__PURE__ */ new Set();
	let fetchControllers = /* @__PURE__ */ new Map();
	let incrementingLoadId = 0;
	let pendingNavigationLoadId = -1;
	let fetchReloadIds = /* @__PURE__ */ new Map();
	let fetchRedirectIds = /* @__PURE__ */ new Set();
	let fetchLoadMatches = /* @__PURE__ */ new Map();
	let activeFetchers = /* @__PURE__ */ new Map();
	let deletedFetchers = /* @__PURE__ */ new Set();
	let activeDeferreds = /* @__PURE__ */ new Map();
	let blockerFunctions = /* @__PURE__ */ new Map();
	let unblockBlockerHistoryUpdate = void 0;
	function initialize() {
		unlistenHistory = init.history.listen((_ref) => {
			let { action: historyAction, location, delta } = _ref;
			if (unblockBlockerHistoryUpdate) {
				unblockBlockerHistoryUpdate();
				unblockBlockerHistoryUpdate = void 0;
				return;
			}
			warning(blockerFunctions.size === 0 || delta != null, "You are trying to use a blocker on a POP navigation to a location that was not created by @remix-run/router. This will fail silently in production. This can happen if you are navigating outside the router via `window.history.pushState`/`window.location.hash` instead of using router navigation APIs.  This can also happen if you are using createHashRouter and the user manually changes the URL.");
			let blockerKey = shouldBlockNavigation({
				currentLocation: state.location,
				nextLocation: location,
				historyAction
			});
			if (blockerKey && delta != null) {
				let nextHistoryUpdatePromise = new Promise((resolve) => {
					unblockBlockerHistoryUpdate = resolve;
				});
				init.history.go(delta * -1);
				updateBlocker(blockerKey, {
					state: "blocked",
					location,
					proceed() {
						updateBlocker(blockerKey, {
							state: "proceeding",
							proceed: void 0,
							reset: void 0,
							location
						});
						nextHistoryUpdatePromise.then(() => init.history.go(delta));
					},
					reset() {
						let blockers = new Map(state.blockers);
						blockers.set(blockerKey, IDLE_BLOCKER);
						updateState({ blockers });
					}
				});
				return;
			}
			return startNavigation(historyAction, location);
		});
		if (isBrowser) {
			restoreAppliedTransitions(routerWindow, appliedViewTransitions);
			let _saveAppliedTransitions = () => persistAppliedTransitions(routerWindow, appliedViewTransitions);
			routerWindow.addEventListener("pagehide", _saveAppliedTransitions);
			removePageHideEventListener = () => routerWindow.removeEventListener("pagehide", _saveAppliedTransitions);
		}
		if (!state.initialized) startNavigation(Action.Pop, state.location, { initialHydration: true });
		return router;
	}
	function dispose() {
		if (unlistenHistory) unlistenHistory();
		if (removePageHideEventListener) removePageHideEventListener();
		subscribers.clear();
		pendingNavigationController && pendingNavigationController.abort();
		state.fetchers.forEach((_, key) => deleteFetcher(key));
		state.blockers.forEach((_, key) => deleteBlocker(key));
	}
	function subscribe(fn) {
		subscribers.add(fn);
		return () => subscribers.delete(fn);
	}
	function updateState(newState, opts) {
		if (opts === void 0) opts = {};
		state = _extends$2({}, state, newState);
		let completedFetchers = [];
		let deletedFetchersKeys = [];
		if (future.v7_fetcherPersist) state.fetchers.forEach((fetcher, key) => {
			if (fetcher.state === "idle") if (deletedFetchers.has(key)) deletedFetchersKeys.push(key);
			else completedFetchers.push(key);
		});
		deletedFetchers.forEach((key) => {
			if (!state.fetchers.has(key) && !fetchControllers.has(key)) deletedFetchersKeys.push(key);
		});
		[...subscribers].forEach((subscriber) => subscriber(state, {
			deletedFetchers: deletedFetchersKeys,
			viewTransitionOpts: opts.viewTransitionOpts,
			flushSync: opts.flushSync === true
		}));
		if (future.v7_fetcherPersist) {
			completedFetchers.forEach((key) => state.fetchers.delete(key));
			deletedFetchersKeys.forEach((key) => deleteFetcher(key));
		} else deletedFetchersKeys.forEach((key) => deletedFetchers.delete(key));
	}
	function completeNavigation(location, newState, _temp) {
		var _location$state, _location$state2;
		let { flushSync } = _temp === void 0 ? {} : _temp;
		let isActionReload = state.actionData != null && state.navigation.formMethod != null && isMutationMethod(state.navigation.formMethod) && state.navigation.state === "loading" && ((_location$state = location.state) == null ? void 0 : _location$state._isRedirect) !== true;
		let actionData;
		if (newState.actionData) if (Object.keys(newState.actionData).length > 0) actionData = newState.actionData;
		else actionData = null;
		else if (isActionReload) actionData = state.actionData;
		else actionData = null;
		let loaderData = newState.loaderData ? mergeLoaderData(state.loaderData, newState.loaderData, newState.matches || [], newState.errors) : state.loaderData;
		let blockers = state.blockers;
		if (blockers.size > 0) {
			blockers = new Map(blockers);
			blockers.forEach((_, k) => blockers.set(k, IDLE_BLOCKER));
		}
		let preventScrollReset = pendingPreventScrollReset === true || state.navigation.formMethod != null && isMutationMethod(state.navigation.formMethod) && ((_location$state2 = location.state) == null ? void 0 : _location$state2._isRedirect) !== true;
		if (inFlightDataRoutes) {
			dataRoutes = inFlightDataRoutes;
			inFlightDataRoutes = void 0;
		}
		if (isUninterruptedRevalidation);
		else if (pendingAction === Action.Pop);
		else if (pendingAction === Action.Push) init.history.push(location, location.state);
		else if (pendingAction === Action.Replace) init.history.replace(location, location.state);
		let viewTransitionOpts;
		if (pendingAction === Action.Pop) {
			let priorPaths = appliedViewTransitions.get(state.location.pathname);
			if (priorPaths && priorPaths.has(location.pathname)) viewTransitionOpts = {
				currentLocation: state.location,
				nextLocation: location
			};
			else if (appliedViewTransitions.has(location.pathname)) viewTransitionOpts = {
				currentLocation: location,
				nextLocation: state.location
			};
		} else if (pendingViewTransitionEnabled) {
			let toPaths = appliedViewTransitions.get(state.location.pathname);
			if (toPaths) toPaths.add(location.pathname);
			else {
				toPaths = new Set([location.pathname]);
				appliedViewTransitions.set(state.location.pathname, toPaths);
			}
			viewTransitionOpts = {
				currentLocation: state.location,
				nextLocation: location
			};
		}
		updateState(_extends$2({}, newState, {
			actionData,
			loaderData,
			historyAction: pendingAction,
			location,
			initialized: true,
			navigation: IDLE_NAVIGATION,
			revalidation: "idle",
			restoreScrollPosition: getSavedScrollPosition(location, newState.matches || state.matches),
			preventScrollReset,
			blockers
		}), {
			viewTransitionOpts,
			flushSync: flushSync === true
		});
		pendingAction = Action.Pop;
		pendingPreventScrollReset = false;
		pendingViewTransitionEnabled = false;
		isUninterruptedRevalidation = false;
		isRevalidationRequired = false;
		cancelledDeferredRoutes = [];
	}
	async function navigate(to, opts) {
		if (typeof to === "number") {
			init.history.go(to);
			return;
		}
		let normalizedPath = normalizeTo(state.location, state.matches, basename, future.v7_prependBasename, to, future.v7_relativeSplatPath, opts == null ? void 0 : opts.fromRouteId, opts == null ? void 0 : opts.relative);
		let { path, submission, error } = normalizeNavigateOptions(future.v7_normalizeFormMethod, false, normalizedPath, opts);
		let currentLocation = state.location;
		let nextLocation = createLocation(state.location, path, opts && opts.state);
		nextLocation = _extends$2({}, nextLocation, init.history.encodeLocation(nextLocation));
		let userReplace = opts && opts.replace != null ? opts.replace : void 0;
		let historyAction = Action.Push;
		if (userReplace === true) historyAction = Action.Replace;
		else if (userReplace === false);
		else if (submission != null && isMutationMethod(submission.formMethod) && submission.formAction === state.location.pathname + state.location.search) historyAction = Action.Replace;
		let preventScrollReset = opts && "preventScrollReset" in opts ? opts.preventScrollReset === true : void 0;
		let flushSync = (opts && opts.flushSync) === true;
		let blockerKey = shouldBlockNavigation({
			currentLocation,
			nextLocation,
			historyAction
		});
		if (blockerKey) {
			updateBlocker(blockerKey, {
				state: "blocked",
				location: nextLocation,
				proceed() {
					updateBlocker(blockerKey, {
						state: "proceeding",
						proceed: void 0,
						reset: void 0,
						location: nextLocation
					});
					navigate(to, opts);
				},
				reset() {
					let blockers = new Map(state.blockers);
					blockers.set(blockerKey, IDLE_BLOCKER);
					updateState({ blockers });
				}
			});
			return;
		}
		return await startNavigation(historyAction, nextLocation, {
			submission,
			pendingError: error,
			preventScrollReset,
			replace: opts && opts.replace,
			enableViewTransition: opts && opts.viewTransition,
			flushSync
		});
	}
	function revalidate() {
		interruptActiveLoads();
		updateState({ revalidation: "loading" });
		if (state.navigation.state === "submitting") return;
		if (state.navigation.state === "idle") {
			startNavigation(state.historyAction, state.location, { startUninterruptedRevalidation: true });
			return;
		}
		startNavigation(pendingAction || state.historyAction, state.navigation.location, {
			overrideNavigation: state.navigation,
			enableViewTransition: pendingViewTransitionEnabled === true
		});
	}
	async function startNavigation(historyAction, location, opts) {
		pendingNavigationController && pendingNavigationController.abort();
		pendingNavigationController = null;
		pendingAction = historyAction;
		isUninterruptedRevalidation = (opts && opts.startUninterruptedRevalidation) === true;
		saveScrollPosition(state.location, state.matches);
		pendingPreventScrollReset = (opts && opts.preventScrollReset) === true;
		pendingViewTransitionEnabled = (opts && opts.enableViewTransition) === true;
		let routesToUse = inFlightDataRoutes || dataRoutes;
		let loadingNavigation = opts && opts.overrideNavigation;
		let matches = opts != null && opts.initialHydration && state.matches && state.matches.length > 0 && !initialMatchesIsFOW ? state.matches : matchRoutes(routesToUse, location, basename);
		let flushSync = (opts && opts.flushSync) === true;
		if (matches && state.initialized && !isRevalidationRequired && isHashChangeOnly(state.location, location) && !(opts && opts.submission && isMutationMethod(opts.submission.formMethod))) {
			completeNavigation(location, { matches }, { flushSync });
			return;
		}
		let fogOfWar = checkFogOfWar(matches, routesToUse, location.pathname);
		if (fogOfWar.active && fogOfWar.matches) matches = fogOfWar.matches;
		if (!matches) {
			let { error, notFoundMatches, route } = handleNavigational404(location.pathname);
			completeNavigation(location, {
				matches: notFoundMatches,
				loaderData: {},
				errors: { [route.id]: error }
			}, { flushSync });
			return;
		}
		pendingNavigationController = new AbortController();
		let request = createClientSideRequest(init.history, location, pendingNavigationController.signal, opts && opts.submission);
		let pendingActionResult;
		if (opts && opts.pendingError) pendingActionResult = [findNearestBoundary(matches).route.id, {
			type: ResultType.error,
			error: opts.pendingError
		}];
		else if (opts && opts.submission && isMutationMethod(opts.submission.formMethod)) {
			let actionResult = await handleAction(request, location, opts.submission, matches, fogOfWar.active, {
				replace: opts.replace,
				flushSync
			});
			if (actionResult.shortCircuited) return;
			if (actionResult.pendingActionResult) {
				let [routeId, result] = actionResult.pendingActionResult;
				if (isErrorResult(result) && isRouteErrorResponse(result.error) && result.error.status === 404) {
					pendingNavigationController = null;
					completeNavigation(location, {
						matches: actionResult.matches,
						loaderData: {},
						errors: { [routeId]: result.error }
					});
					return;
				}
			}
			matches = actionResult.matches || matches;
			pendingActionResult = actionResult.pendingActionResult;
			loadingNavigation = getLoadingNavigation(location, opts.submission);
			flushSync = false;
			fogOfWar.active = false;
			request = createClientSideRequest(init.history, request.url, request.signal);
		}
		let { shortCircuited, matches: updatedMatches, loaderData, errors } = await handleLoaders(request, location, matches, fogOfWar.active, loadingNavigation, opts && opts.submission, opts && opts.fetcherSubmission, opts && opts.replace, opts && opts.initialHydration === true, flushSync, pendingActionResult);
		if (shortCircuited) return;
		pendingNavigationController = null;
		completeNavigation(location, _extends$2({ matches: updatedMatches || matches }, getActionDataForCommit(pendingActionResult), {
			loaderData,
			errors
		}));
	}
	async function handleAction(request, location, submission, matches, isFogOfWar, opts) {
		if (opts === void 0) opts = {};
		interruptActiveLoads();
		updateState({ navigation: getSubmittingNavigation(location, submission) }, { flushSync: opts.flushSync === true });
		if (isFogOfWar) {
			let discoverResult = await discoverRoutes(matches, location.pathname, request.signal);
			if (discoverResult.type === "aborted") return { shortCircuited: true };
			else if (discoverResult.type === "error") {
				let boundaryId = findNearestBoundary(discoverResult.partialMatches).route.id;
				return {
					matches: discoverResult.partialMatches,
					pendingActionResult: [boundaryId, {
						type: ResultType.error,
						error: discoverResult.error
					}]
				};
			} else if (!discoverResult.matches) {
				let { notFoundMatches, error, route } = handleNavigational404(location.pathname);
				return {
					matches: notFoundMatches,
					pendingActionResult: [route.id, {
						type: ResultType.error,
						error
					}]
				};
			} else matches = discoverResult.matches;
		}
		let result;
		let actionMatch = getTargetMatch(matches, location);
		if (!actionMatch.route.action && !actionMatch.route.lazy) result = {
			type: ResultType.error,
			error: getInternalRouterError(405, {
				method: request.method,
				pathname: location.pathname,
				routeId: actionMatch.route.id
			})
		};
		else {
			result = (await callDataStrategy("action", state, request, [actionMatch], matches, null))[actionMatch.route.id];
			if (request.signal.aborted) return { shortCircuited: true };
		}
		if (isRedirectResult(result)) {
			let replace;
			if (opts && opts.replace != null) replace = opts.replace;
			else replace = normalizeRedirectLocation(result.response.headers.get("Location"), new URL(request.url), basename, init.history) === state.location.pathname + state.location.search;
			await startRedirectNavigation(request, result, true, {
				submission,
				replace
			});
			return { shortCircuited: true };
		}
		if (isDeferredResult(result)) throw getInternalRouterError(400, { type: "defer-action" });
		if (isErrorResult(result)) {
			let boundaryMatch = findNearestBoundary(matches, actionMatch.route.id);
			if ((opts && opts.replace) !== true) pendingAction = Action.Push;
			return {
				matches,
				pendingActionResult: [boundaryMatch.route.id, result]
			};
		}
		return {
			matches,
			pendingActionResult: [actionMatch.route.id, result]
		};
	}
	async function handleLoaders(request, location, matches, isFogOfWar, overrideNavigation, submission, fetcherSubmission, replace, initialHydration, flushSync, pendingActionResult) {
		let loadingNavigation = overrideNavigation || getLoadingNavigation(location, submission);
		let activeSubmission = submission || fetcherSubmission || getSubmissionFromNavigation(loadingNavigation);
		let shouldUpdateNavigationState = !isUninterruptedRevalidation && (!future.v7_partialHydration || !initialHydration);
		if (isFogOfWar) {
			if (shouldUpdateNavigationState) {
				let actionData = getUpdatedActionData(pendingActionResult);
				updateState(_extends$2({ navigation: loadingNavigation }, actionData !== void 0 ? { actionData } : {}), { flushSync });
			}
			let discoverResult = await discoverRoutes(matches, location.pathname, request.signal);
			if (discoverResult.type === "aborted") return { shortCircuited: true };
			else if (discoverResult.type === "error") {
				let boundaryId = findNearestBoundary(discoverResult.partialMatches).route.id;
				return {
					matches: discoverResult.partialMatches,
					loaderData: {},
					errors: { [boundaryId]: discoverResult.error }
				};
			} else if (!discoverResult.matches) {
				let { error, notFoundMatches, route } = handleNavigational404(location.pathname);
				return {
					matches: notFoundMatches,
					loaderData: {},
					errors: { [route.id]: error }
				};
			} else matches = discoverResult.matches;
		}
		let routesToUse = inFlightDataRoutes || dataRoutes;
		let [matchesToLoad, revalidatingFetchers] = getMatchesToLoad(init.history, state, matches, activeSubmission, location, future.v7_partialHydration && initialHydration === true, future.v7_skipActionErrorRevalidation, isRevalidationRequired, cancelledDeferredRoutes, cancelledFetcherLoads, deletedFetchers, fetchLoadMatches, fetchRedirectIds, routesToUse, basename, pendingActionResult);
		cancelActiveDeferreds((routeId) => !(matches && matches.some((m) => m.route.id === routeId)) || matchesToLoad && matchesToLoad.some((m) => m.route.id === routeId));
		pendingNavigationLoadId = ++incrementingLoadId;
		if (matchesToLoad.length === 0 && revalidatingFetchers.length === 0) {
			let updatedFetchers = markFetchRedirectsDone();
			completeNavigation(location, _extends$2({
				matches,
				loaderData: {},
				errors: pendingActionResult && isErrorResult(pendingActionResult[1]) ? { [pendingActionResult[0]]: pendingActionResult[1].error } : null
			}, getActionDataForCommit(pendingActionResult), updatedFetchers ? { fetchers: new Map(state.fetchers) } : {}), { flushSync });
			return { shortCircuited: true };
		}
		if (shouldUpdateNavigationState) {
			let updates = {};
			if (!isFogOfWar) {
				updates.navigation = loadingNavigation;
				let actionData = getUpdatedActionData(pendingActionResult);
				if (actionData !== void 0) updates.actionData = actionData;
			}
			if (revalidatingFetchers.length > 0) updates.fetchers = getUpdatedRevalidatingFetchers(revalidatingFetchers);
			updateState(updates, { flushSync });
		}
		revalidatingFetchers.forEach((rf) => {
			abortFetcher(rf.key);
			if (rf.controller) fetchControllers.set(rf.key, rf.controller);
		});
		let abortPendingFetchRevalidations = () => revalidatingFetchers.forEach((f) => abortFetcher(f.key));
		if (pendingNavigationController) pendingNavigationController.signal.addEventListener("abort", abortPendingFetchRevalidations);
		let { loaderResults, fetcherResults } = await callLoadersAndMaybeResolveData(state, matches, matchesToLoad, revalidatingFetchers, request);
		if (request.signal.aborted) return { shortCircuited: true };
		if (pendingNavigationController) pendingNavigationController.signal.removeEventListener("abort", abortPendingFetchRevalidations);
		revalidatingFetchers.forEach((rf) => fetchControllers.delete(rf.key));
		let redirect = findRedirect(loaderResults);
		if (redirect) {
			await startRedirectNavigation(request, redirect.result, true, { replace });
			return { shortCircuited: true };
		}
		redirect = findRedirect(fetcherResults);
		if (redirect) {
			fetchRedirectIds.add(redirect.key);
			await startRedirectNavigation(request, redirect.result, true, { replace });
			return { shortCircuited: true };
		}
		let { loaderData, errors } = processLoaderData(state, matches, loaderResults, pendingActionResult, revalidatingFetchers, fetcherResults, activeDeferreds);
		activeDeferreds.forEach((deferredData, routeId) => {
			deferredData.subscribe((aborted) => {
				if (aborted || deferredData.done) activeDeferreds.delete(routeId);
			});
		});
		if (future.v7_partialHydration && initialHydration && state.errors) errors = _extends$2({}, state.errors, errors);
		let updatedFetchers = markFetchRedirectsDone();
		let didAbortFetchLoads = abortStaleFetchLoads(pendingNavigationLoadId);
		let shouldUpdateFetchers = updatedFetchers || didAbortFetchLoads || revalidatingFetchers.length > 0;
		return _extends$2({
			matches,
			loaderData,
			errors
		}, shouldUpdateFetchers ? { fetchers: new Map(state.fetchers) } : {});
	}
	function getUpdatedActionData(pendingActionResult) {
		if (pendingActionResult && !isErrorResult(pendingActionResult[1])) return { [pendingActionResult[0]]: pendingActionResult[1].data };
		else if (state.actionData) if (Object.keys(state.actionData).length === 0) return null;
		else return state.actionData;
	}
	function getUpdatedRevalidatingFetchers(revalidatingFetchers) {
		revalidatingFetchers.forEach((rf) => {
			let fetcher = state.fetchers.get(rf.key);
			let revalidatingFetcher = getLoadingFetcher(void 0, fetcher ? fetcher.data : void 0);
			state.fetchers.set(rf.key, revalidatingFetcher);
		});
		return new Map(state.fetchers);
	}
	function fetch(key, routeId, href, opts) {
		if (isServer) throw new Error("router.fetch() was called during the server render, but it shouldn't be. You are likely calling a useFetcher() method in the body of your component. Try moving it to a useEffect or a callback.");
		abortFetcher(key);
		let flushSync = (opts && opts.flushSync) === true;
		let routesToUse = inFlightDataRoutes || dataRoutes;
		let normalizedPath = normalizeTo(state.location, state.matches, basename, future.v7_prependBasename, href, future.v7_relativeSplatPath, routeId, opts == null ? void 0 : opts.relative);
		let matches = matchRoutes(routesToUse, normalizedPath, basename);
		let fogOfWar = checkFogOfWar(matches, routesToUse, normalizedPath);
		if (fogOfWar.active && fogOfWar.matches) matches = fogOfWar.matches;
		if (!matches) {
			setFetcherError(key, routeId, getInternalRouterError(404, { pathname: normalizedPath }), { flushSync });
			return;
		}
		let { path, submission, error } = normalizeNavigateOptions(future.v7_normalizeFormMethod, true, normalizedPath, opts);
		if (error) {
			setFetcherError(key, routeId, error, { flushSync });
			return;
		}
		let match = getTargetMatch(matches, path);
		let preventScrollReset = (opts && opts.preventScrollReset) === true;
		if (submission && isMutationMethod(submission.formMethod)) {
			handleFetcherAction(key, routeId, path, match, matches, fogOfWar.active, flushSync, preventScrollReset, submission);
			return;
		}
		fetchLoadMatches.set(key, {
			routeId,
			path
		});
		handleFetcherLoader(key, routeId, path, match, matches, fogOfWar.active, flushSync, preventScrollReset, submission);
	}
	async function handleFetcherAction(key, routeId, path, match, requestMatches, isFogOfWar, flushSync, preventScrollReset, submission) {
		interruptActiveLoads();
		fetchLoadMatches.delete(key);
		function detectAndHandle405Error(m) {
			if (!m.route.action && !m.route.lazy) {
				setFetcherError(key, routeId, getInternalRouterError(405, {
					method: submission.formMethod,
					pathname: path,
					routeId
				}), { flushSync });
				return true;
			}
			return false;
		}
		if (!isFogOfWar && detectAndHandle405Error(match)) return;
		updateFetcherState(key, getSubmittingFetcher(submission, state.fetchers.get(key)), { flushSync });
		let abortController = new AbortController();
		let fetchRequest = createClientSideRequest(init.history, path, abortController.signal, submission);
		if (isFogOfWar) {
			let discoverResult = await discoverRoutes(requestMatches, new URL(fetchRequest.url).pathname, fetchRequest.signal, key);
			if (discoverResult.type === "aborted") return;
			else if (discoverResult.type === "error") {
				setFetcherError(key, routeId, discoverResult.error, { flushSync });
				return;
			} else if (!discoverResult.matches) {
				setFetcherError(key, routeId, getInternalRouterError(404, { pathname: path }), { flushSync });
				return;
			} else {
				requestMatches = discoverResult.matches;
				match = getTargetMatch(requestMatches, path);
				if (detectAndHandle405Error(match)) return;
			}
		}
		fetchControllers.set(key, abortController);
		let originatingLoadId = incrementingLoadId;
		let actionResult = (await callDataStrategy("action", state, fetchRequest, [match], requestMatches, key))[match.route.id];
		if (fetchRequest.signal.aborted) {
			if (fetchControllers.get(key) === abortController) fetchControllers.delete(key);
			return;
		}
		if (future.v7_fetcherPersist && deletedFetchers.has(key)) {
			if (isRedirectResult(actionResult) || isErrorResult(actionResult)) {
				updateFetcherState(key, getDoneFetcher(void 0));
				return;
			}
		} else {
			if (isRedirectResult(actionResult)) {
				fetchControllers.delete(key);
				if (pendingNavigationLoadId > originatingLoadId) {
					updateFetcherState(key, getDoneFetcher(void 0));
					return;
				} else {
					fetchRedirectIds.add(key);
					updateFetcherState(key, getLoadingFetcher(submission));
					return startRedirectNavigation(fetchRequest, actionResult, false, {
						fetcherSubmission: submission,
						preventScrollReset
					});
				}
			}
			if (isErrorResult(actionResult)) {
				setFetcherError(key, routeId, actionResult.error);
				return;
			}
		}
		if (isDeferredResult(actionResult)) throw getInternalRouterError(400, { type: "defer-action" });
		let nextLocation = state.navigation.location || state.location;
		let revalidationRequest = createClientSideRequest(init.history, nextLocation, abortController.signal);
		let routesToUse = inFlightDataRoutes || dataRoutes;
		let matches = state.navigation.state !== "idle" ? matchRoutes(routesToUse, state.navigation.location, basename) : state.matches;
		invariant(matches, "Didn't find any matches after fetcher action");
		let loadId = ++incrementingLoadId;
		fetchReloadIds.set(key, loadId);
		let loadFetcher = getLoadingFetcher(submission, actionResult.data);
		state.fetchers.set(key, loadFetcher);
		let [matchesToLoad, revalidatingFetchers] = getMatchesToLoad(init.history, state, matches, submission, nextLocation, false, future.v7_skipActionErrorRevalidation, isRevalidationRequired, cancelledDeferredRoutes, cancelledFetcherLoads, deletedFetchers, fetchLoadMatches, fetchRedirectIds, routesToUse, basename, [match.route.id, actionResult]);
		revalidatingFetchers.filter((rf) => rf.key !== key).forEach((rf) => {
			let staleKey = rf.key;
			let existingFetcher = state.fetchers.get(staleKey);
			let revalidatingFetcher = getLoadingFetcher(void 0, existingFetcher ? existingFetcher.data : void 0);
			state.fetchers.set(staleKey, revalidatingFetcher);
			abortFetcher(staleKey);
			if (rf.controller) fetchControllers.set(staleKey, rf.controller);
		});
		updateState({ fetchers: new Map(state.fetchers) });
		let abortPendingFetchRevalidations = () => revalidatingFetchers.forEach((rf) => abortFetcher(rf.key));
		abortController.signal.addEventListener("abort", abortPendingFetchRevalidations);
		let { loaderResults, fetcherResults } = await callLoadersAndMaybeResolveData(state, matches, matchesToLoad, revalidatingFetchers, revalidationRequest);
		if (abortController.signal.aborted) return;
		abortController.signal.removeEventListener("abort", abortPendingFetchRevalidations);
		fetchReloadIds.delete(key);
		fetchControllers.delete(key);
		revalidatingFetchers.forEach((r) => fetchControllers.delete(r.key));
		let redirect = findRedirect(loaderResults);
		if (redirect) return startRedirectNavigation(revalidationRequest, redirect.result, false, { preventScrollReset });
		redirect = findRedirect(fetcherResults);
		if (redirect) {
			fetchRedirectIds.add(redirect.key);
			return startRedirectNavigation(revalidationRequest, redirect.result, false, { preventScrollReset });
		}
		let { loaderData, errors } = processLoaderData(state, matches, loaderResults, void 0, revalidatingFetchers, fetcherResults, activeDeferreds);
		if (state.fetchers.has(key)) {
			let doneFetcher = getDoneFetcher(actionResult.data);
			state.fetchers.set(key, doneFetcher);
		}
		abortStaleFetchLoads(loadId);
		if (state.navigation.state === "loading" && loadId > pendingNavigationLoadId) {
			invariant(pendingAction, "Expected pending action");
			pendingNavigationController && pendingNavigationController.abort();
			completeNavigation(state.navigation.location, {
				matches,
				loaderData,
				errors,
				fetchers: new Map(state.fetchers)
			});
		} else {
			updateState({
				errors,
				loaderData: mergeLoaderData(state.loaderData, loaderData, matches, errors),
				fetchers: new Map(state.fetchers)
			});
			isRevalidationRequired = false;
		}
	}
	async function handleFetcherLoader(key, routeId, path, match, matches, isFogOfWar, flushSync, preventScrollReset, submission) {
		let existingFetcher = state.fetchers.get(key);
		updateFetcherState(key, getLoadingFetcher(submission, existingFetcher ? existingFetcher.data : void 0), { flushSync });
		let abortController = new AbortController();
		let fetchRequest = createClientSideRequest(init.history, path, abortController.signal);
		if (isFogOfWar) {
			let discoverResult = await discoverRoutes(matches, new URL(fetchRequest.url).pathname, fetchRequest.signal, key);
			if (discoverResult.type === "aborted") return;
			else if (discoverResult.type === "error") {
				setFetcherError(key, routeId, discoverResult.error, { flushSync });
				return;
			} else if (!discoverResult.matches) {
				setFetcherError(key, routeId, getInternalRouterError(404, { pathname: path }), { flushSync });
				return;
			} else {
				matches = discoverResult.matches;
				match = getTargetMatch(matches, path);
			}
		}
		fetchControllers.set(key, abortController);
		let originatingLoadId = incrementingLoadId;
		let result = (await callDataStrategy("loader", state, fetchRequest, [match], matches, key))[match.route.id];
		if (isDeferredResult(result)) result = await resolveDeferredData(result, fetchRequest.signal, true) || result;
		if (fetchControllers.get(key) === abortController) fetchControllers.delete(key);
		if (fetchRequest.signal.aborted) return;
		if (deletedFetchers.has(key)) {
			updateFetcherState(key, getDoneFetcher(void 0));
			return;
		}
		if (isRedirectResult(result)) if (pendingNavigationLoadId > originatingLoadId) {
			updateFetcherState(key, getDoneFetcher(void 0));
			return;
		} else {
			fetchRedirectIds.add(key);
			await startRedirectNavigation(fetchRequest, result, false, { preventScrollReset });
			return;
		}
		if (isErrorResult(result)) {
			setFetcherError(key, routeId, result.error);
			return;
		}
		invariant(!isDeferredResult(result), "Unhandled fetcher deferred data");
		updateFetcherState(key, getDoneFetcher(result.data));
	}
	/**
	* Utility function to handle redirects returned from an action or loader.
	* Normally, a redirect "replaces" the navigation that triggered it.  So, for
	* example:
	*
	*  - user is on /a
	*  - user clicks a link to /b
	*  - loader for /b redirects to /c
	*
	* In a non-JS app the browser would track the in-flight navigation to /b and
	* then replace it with /c when it encountered the redirect response.  In
	* the end it would only ever update the URL bar with /c.
	*
	* In client-side routing using pushState/replaceState, we aim to emulate
	* this behavior and we also do not update history until the end of the
	* navigation (including processed redirects).  This means that we never
	* actually touch history until we've processed redirects, so we just use
	* the history action from the original navigation (PUSH or REPLACE).
	*/
	async function startRedirectNavigation(request, redirect, isNavigation, _temp2) {
		let { submission, fetcherSubmission, preventScrollReset, replace } = _temp2 === void 0 ? {} : _temp2;
		if (redirect.response.headers.has("X-Remix-Revalidate")) isRevalidationRequired = true;
		let location = redirect.response.headers.get("Location");
		invariant(location, "Expected a Location header on the redirect Response");
		location = normalizeRedirectLocation(location, new URL(request.url), basename, init.history);
		let redirectLocation = createLocation(state.location, location, { _isRedirect: true });
		if (isBrowser) {
			let isDocumentReload = false;
			if (redirect.response.headers.has("X-Remix-Reload-Document")) isDocumentReload = true;
			else if (ABSOLUTE_URL_REGEX$2.test(location)) {
				const url = init.history.createURL(location);
				isDocumentReload = url.origin !== routerWindow.location.origin || stripBasename(url.pathname, basename) == null;
			}
			if (isDocumentReload) {
				if (replace) routerWindow.location.replace(location);
				else routerWindow.location.assign(location);
				return;
			}
		}
		pendingNavigationController = null;
		let redirectHistoryAction = replace === true || redirect.response.headers.has("X-Remix-Replace") ? Action.Replace : Action.Push;
		let { formMethod, formAction, formEncType } = state.navigation;
		if (!submission && !fetcherSubmission && formMethod && formAction && formEncType) submission = getSubmissionFromNavigation(state.navigation);
		let activeSubmission = submission || fetcherSubmission;
		if (redirectPreserveMethodStatusCodes.has(redirect.response.status) && activeSubmission && isMutationMethod(activeSubmission.formMethod)) await startNavigation(redirectHistoryAction, redirectLocation, {
			submission: _extends$2({}, activeSubmission, { formAction: location }),
			preventScrollReset: preventScrollReset || pendingPreventScrollReset,
			enableViewTransition: isNavigation ? pendingViewTransitionEnabled : void 0
		});
		else await startNavigation(redirectHistoryAction, redirectLocation, {
			overrideNavigation: getLoadingNavigation(redirectLocation, submission),
			fetcherSubmission,
			preventScrollReset: preventScrollReset || pendingPreventScrollReset,
			enableViewTransition: isNavigation ? pendingViewTransitionEnabled : void 0
		});
	}
	async function callDataStrategy(type, state, request, matchesToLoad, matches, fetcherKey) {
		let results;
		let dataResults = {};
		try {
			results = await callDataStrategyImpl(dataStrategyImpl, type, state, request, matchesToLoad, matches, fetcherKey, manifest, mapRouteProperties);
		} catch (e) {
			matchesToLoad.forEach((m) => {
				dataResults[m.route.id] = {
					type: ResultType.error,
					error: e
				};
			});
			return dataResults;
		}
		for (let [routeId, result] of Object.entries(results)) if (isRedirectDataStrategyResultResult(result)) {
			let response = result.result;
			dataResults[routeId] = {
				type: ResultType.redirect,
				response: normalizeRelativeRoutingRedirectResponse(response, request, routeId, matches, basename, future.v7_relativeSplatPath)
			};
		} else dataResults[routeId] = await convertDataStrategyResultToDataResult(result);
		return dataResults;
	}
	async function callLoadersAndMaybeResolveData(state, matches, matchesToLoad, fetchersToLoad, request) {
		let currentMatches = state.matches;
		let loaderResultsPromise = callDataStrategy("loader", state, request, matchesToLoad, matches, null);
		let fetcherResultsPromise = Promise.all(fetchersToLoad.map(async (f) => {
			if (f.matches && f.match && f.controller) {
				let result = (await callDataStrategy("loader", state, createClientSideRequest(init.history, f.path, f.controller.signal), [f.match], f.matches, f.key))[f.match.route.id];
				return { [f.key]: result };
			} else return Promise.resolve({ [f.key]: {
				type: ResultType.error,
				error: getInternalRouterError(404, { pathname: f.path })
			} });
		}));
		let loaderResults = await loaderResultsPromise;
		let fetcherResults = (await fetcherResultsPromise).reduce((acc, r) => Object.assign(acc, r), {});
		await Promise.all([resolveNavigationDeferredResults(matches, loaderResults, request.signal, currentMatches, state.loaderData), resolveFetcherDeferredResults(matches, fetcherResults, fetchersToLoad)]);
		return {
			loaderResults,
			fetcherResults
		};
	}
	function interruptActiveLoads() {
		isRevalidationRequired = true;
		cancelledDeferredRoutes.push(...cancelActiveDeferreds());
		fetchLoadMatches.forEach((_, key) => {
			if (fetchControllers.has(key)) cancelledFetcherLoads.add(key);
			abortFetcher(key);
		});
	}
	function updateFetcherState(key, fetcher, opts) {
		if (opts === void 0) opts = {};
		state.fetchers.set(key, fetcher);
		updateState({ fetchers: new Map(state.fetchers) }, { flushSync: (opts && opts.flushSync) === true });
	}
	function setFetcherError(key, routeId, error, opts) {
		if (opts === void 0) opts = {};
		let boundaryMatch = findNearestBoundary(state.matches, routeId);
		deleteFetcher(key);
		updateState({
			errors: { [boundaryMatch.route.id]: error },
			fetchers: new Map(state.fetchers)
		}, { flushSync: (opts && opts.flushSync) === true });
	}
	function getFetcher(key) {
		activeFetchers.set(key, (activeFetchers.get(key) || 0) + 1);
		if (deletedFetchers.has(key)) deletedFetchers.delete(key);
		return state.fetchers.get(key) || IDLE_FETCHER;
	}
	function deleteFetcher(key) {
		let fetcher = state.fetchers.get(key);
		if (fetchControllers.has(key) && !(fetcher && fetcher.state === "loading" && fetchReloadIds.has(key))) abortFetcher(key);
		fetchLoadMatches.delete(key);
		fetchReloadIds.delete(key);
		fetchRedirectIds.delete(key);
		if (future.v7_fetcherPersist) deletedFetchers.delete(key);
		cancelledFetcherLoads.delete(key);
		state.fetchers.delete(key);
	}
	function deleteFetcherAndUpdateState(key) {
		let count = (activeFetchers.get(key) || 0) - 1;
		if (count <= 0) {
			activeFetchers.delete(key);
			deletedFetchers.add(key);
			if (!future.v7_fetcherPersist) deleteFetcher(key);
		} else activeFetchers.set(key, count);
		updateState({ fetchers: new Map(state.fetchers) });
	}
	function abortFetcher(key) {
		let controller = fetchControllers.get(key);
		if (controller) {
			controller.abort();
			fetchControllers.delete(key);
		}
	}
	function markFetchersDone(keys) {
		for (let key of keys) {
			let doneFetcher = getDoneFetcher(getFetcher(key).data);
			state.fetchers.set(key, doneFetcher);
		}
	}
	function markFetchRedirectsDone() {
		let doneKeys = [];
		let updatedFetchers = false;
		for (let key of fetchRedirectIds) {
			let fetcher = state.fetchers.get(key);
			invariant(fetcher, "Expected fetcher: " + key);
			if (fetcher.state === "loading") {
				fetchRedirectIds.delete(key);
				doneKeys.push(key);
				updatedFetchers = true;
			}
		}
		markFetchersDone(doneKeys);
		return updatedFetchers;
	}
	function abortStaleFetchLoads(landedId) {
		let yeetedKeys = [];
		for (let [key, id] of fetchReloadIds) if (id < landedId) {
			let fetcher = state.fetchers.get(key);
			invariant(fetcher, "Expected fetcher: " + key);
			if (fetcher.state === "loading") {
				abortFetcher(key);
				fetchReloadIds.delete(key);
				yeetedKeys.push(key);
			}
		}
		markFetchersDone(yeetedKeys);
		return yeetedKeys.length > 0;
	}
	function getBlocker(key, fn) {
		let blocker = state.blockers.get(key) || IDLE_BLOCKER;
		if (blockerFunctions.get(key) !== fn) blockerFunctions.set(key, fn);
		return blocker;
	}
	function deleteBlocker(key) {
		state.blockers.delete(key);
		blockerFunctions.delete(key);
	}
	function updateBlocker(key, newBlocker) {
		let blocker = state.blockers.get(key) || IDLE_BLOCKER;
		invariant(blocker.state === "unblocked" && newBlocker.state === "blocked" || blocker.state === "blocked" && newBlocker.state === "blocked" || blocker.state === "blocked" && newBlocker.state === "proceeding" || blocker.state === "blocked" && newBlocker.state === "unblocked" || blocker.state === "proceeding" && newBlocker.state === "unblocked", "Invalid blocker state transition: " + blocker.state + " -> " + newBlocker.state);
		let blockers = new Map(state.blockers);
		blockers.set(key, newBlocker);
		updateState({ blockers });
	}
	function shouldBlockNavigation(_ref2) {
		let { currentLocation, nextLocation, historyAction } = _ref2;
		if (blockerFunctions.size === 0) return;
		if (blockerFunctions.size > 1) warning(false, "A router only supports one blocker at a time");
		let entries = Array.from(blockerFunctions.entries());
		let [blockerKey, blockerFunction] = entries[entries.length - 1];
		let blocker = state.blockers.get(blockerKey);
		if (blocker && blocker.state === "proceeding") return;
		if (blockerFunction({
			currentLocation,
			nextLocation,
			historyAction
		})) return blockerKey;
	}
	function handleNavigational404(pathname) {
		let error = getInternalRouterError(404, { pathname });
		let { matches, route } = getShortCircuitMatches(inFlightDataRoutes || dataRoutes);
		cancelActiveDeferreds();
		return {
			notFoundMatches: matches,
			route,
			error
		};
	}
	function cancelActiveDeferreds(predicate) {
		let cancelledRouteIds = [];
		activeDeferreds.forEach((dfd, routeId) => {
			if (!predicate || predicate(routeId)) {
				dfd.cancel();
				cancelledRouteIds.push(routeId);
				activeDeferreds.delete(routeId);
			}
		});
		return cancelledRouteIds;
	}
	function enableScrollRestoration(positions, getPosition, getKey) {
		savedScrollPositions = positions;
		getScrollPosition = getPosition;
		getScrollRestorationKey = getKey || null;
		if (!initialScrollRestored && state.navigation === IDLE_NAVIGATION) {
			initialScrollRestored = true;
			let y = getSavedScrollPosition(state.location, state.matches);
			if (y != null) updateState({ restoreScrollPosition: y });
		}
		return () => {
			savedScrollPositions = null;
			getScrollPosition = null;
			getScrollRestorationKey = null;
		};
	}
	function getScrollKey(location, matches) {
		if (getScrollRestorationKey) return getScrollRestorationKey(location, matches.map((m) => convertRouteMatchToUiMatch(m, state.loaderData))) || location.key;
		return location.key;
	}
	function saveScrollPosition(location, matches) {
		if (savedScrollPositions && getScrollPosition) {
			let key = getScrollKey(location, matches);
			savedScrollPositions[key] = getScrollPosition();
		}
	}
	function getSavedScrollPosition(location, matches) {
		if (savedScrollPositions) {
			let key = getScrollKey(location, matches);
			let y = savedScrollPositions[key];
			if (typeof y === "number") return y;
		}
		return null;
	}
	function checkFogOfWar(matches, routesToUse, pathname) {
		if (patchRoutesOnNavigationImpl) {
			if (!matches) return {
				active: true,
				matches: matchRoutesImpl(routesToUse, pathname, basename, true) || []
			};
			else if (Object.keys(matches[0].params).length > 0) return {
				active: true,
				matches: matchRoutesImpl(routesToUse, pathname, basename, true)
			};
		}
		return {
			active: false,
			matches: null
		};
	}
	async function discoverRoutes(matches, pathname, signal, fetcherKey) {
		if (!patchRoutesOnNavigationImpl) return {
			type: "success",
			matches
		};
		let partialMatches = matches;
		while (true) {
			let isNonHMR = inFlightDataRoutes == null;
			let routesToUse = inFlightDataRoutes || dataRoutes;
			let localManifest = manifest;
			try {
				await patchRoutesOnNavigationImpl({
					signal,
					path: pathname,
					matches: partialMatches,
					fetcherKey,
					patch: (routeId, children) => {
						if (signal.aborted) return;
						patchRoutesImpl(routeId, children, routesToUse, localManifest, mapRouteProperties);
					}
				});
			} catch (e) {
				return {
					type: "error",
					error: e,
					partialMatches
				};
			} finally {
				if (isNonHMR && !signal.aborted) dataRoutes = [...dataRoutes];
			}
			if (signal.aborted) return { type: "aborted" };
			let newMatches = matchRoutes(routesToUse, pathname, basename);
			if (newMatches) return {
				type: "success",
				matches: newMatches
			};
			let newPartialMatches = matchRoutesImpl(routesToUse, pathname, basename, true);
			if (!newPartialMatches || partialMatches.length === newPartialMatches.length && partialMatches.every((m, i) => m.route.id === newPartialMatches[i].route.id)) return {
				type: "success",
				matches: null
			};
			partialMatches = newPartialMatches;
		}
	}
	function _internalSetRoutes(newRoutes) {
		manifest = {};
		inFlightDataRoutes = convertRoutesToDataRoutes(newRoutes, mapRouteProperties, void 0, manifest);
	}
	function patchRoutes(routeId, children) {
		let isNonHMR = inFlightDataRoutes == null;
		patchRoutesImpl(routeId, children, inFlightDataRoutes || dataRoutes, manifest, mapRouteProperties);
		if (isNonHMR) {
			dataRoutes = [...dataRoutes];
			updateState({});
		}
	}
	router = {
		get basename() {
			return basename;
		},
		get future() {
			return future;
		},
		get state() {
			return state;
		},
		get routes() {
			return dataRoutes;
		},
		get window() {
			return routerWindow;
		},
		initialize,
		subscribe,
		enableScrollRestoration,
		navigate,
		fetch,
		revalidate,
		createHref: (to) => init.history.createHref(to),
		encodeLocation: (to) => init.history.encodeLocation(to),
		getFetcher,
		deleteFetcher: deleteFetcherAndUpdateState,
		dispose,
		getBlocker,
		deleteBlocker,
		patchRoutes,
		_internalFetchControllers: fetchControllers,
		_internalActiveDeferreds: activeDeferreds,
		_internalSetRoutes
	};
	return router;
}
function isSubmissionNavigation(opts) {
	return opts != null && ("formData" in opts && opts.formData != null || "body" in opts && opts.body !== void 0);
}
function normalizeTo(location, matches, basename, prependBasename, to, v7_relativeSplatPath, fromRouteId, relative) {
	let contextualMatches;
	let activeRouteMatch;
	if (fromRouteId) {
		contextualMatches = [];
		for (let match of matches) {
			contextualMatches.push(match);
			if (match.route.id === fromRouteId) {
				activeRouteMatch = match;
				break;
			}
		}
	} else {
		contextualMatches = matches;
		activeRouteMatch = matches[matches.length - 1];
	}
	let path = resolveTo(to ? to : ".", getResolveToMatches(contextualMatches, v7_relativeSplatPath), stripBasename(location.pathname, basename) || location.pathname, relative === "path");
	if (to == null) {
		path.search = location.search;
		path.hash = location.hash;
	}
	if ((to == null || to === "" || to === ".") && activeRouteMatch) {
		let nakedIndex = hasNakedIndexQuery(path.search);
		if (activeRouteMatch.route.index && !nakedIndex) path.search = path.search ? path.search.replace(/^\?/, "?index&") : "?index";
		else if (!activeRouteMatch.route.index && nakedIndex) {
			let params = new URLSearchParams(path.search);
			let indexValues = params.getAll("index");
			params.delete("index");
			indexValues.filter((v) => v).forEach((v) => params.append("index", v));
			let qs = params.toString();
			path.search = qs ? "?" + qs : "";
		}
	}
	if (prependBasename && basename !== "/") path.pathname = path.pathname === "/" ? basename : joinPaths([basename, path.pathname]);
	return createPath(path);
}
function normalizeNavigateOptions(normalizeFormMethod, isFetcher, path, opts) {
	if (!opts || !isSubmissionNavigation(opts)) return { path };
	if (opts.formMethod && !isValidMethod(opts.formMethod)) return {
		path,
		error: getInternalRouterError(405, { method: opts.formMethod })
	};
	let getInvalidBodyError = () => ({
		path,
		error: getInternalRouterError(400, { type: "invalid-body" })
	});
	let rawFormMethod = opts.formMethod || "get";
	let formMethod = normalizeFormMethod ? rawFormMethod.toUpperCase() : rawFormMethod.toLowerCase();
	let formAction = stripHashFromPath(path);
	if (opts.body !== void 0) {
		if (opts.formEncType === "text/plain") {
			if (!isMutationMethod(formMethod)) return getInvalidBodyError();
			let text = typeof opts.body === "string" ? opts.body : opts.body instanceof FormData || opts.body instanceof URLSearchParams ? Array.from(opts.body.entries()).reduce((acc, _ref3) => {
				let [name, value] = _ref3;
				return "" + acc + name + "=" + value + "\n";
			}, "") : String(opts.body);
			return {
				path,
				submission: {
					formMethod,
					formAction,
					formEncType: opts.formEncType,
					formData: void 0,
					json: void 0,
					text
				}
			};
		} else if (opts.formEncType === "application/json") {
			if (!isMutationMethod(formMethod)) return getInvalidBodyError();
			try {
				let json = typeof opts.body === "string" ? JSON.parse(opts.body) : opts.body;
				return {
					path,
					submission: {
						formMethod,
						formAction,
						formEncType: opts.formEncType,
						formData: void 0,
						json,
						text: void 0
					}
				};
			} catch (e) {
				return getInvalidBodyError();
			}
		}
	}
	invariant(typeof FormData === "function", "FormData is not available in this environment");
	let searchParams;
	let formData;
	if (opts.formData) {
		searchParams = convertFormDataToSearchParams(opts.formData);
		formData = opts.formData;
	} else if (opts.body instanceof FormData) {
		searchParams = convertFormDataToSearchParams(opts.body);
		formData = opts.body;
	} else if (opts.body instanceof URLSearchParams) {
		searchParams = opts.body;
		formData = convertSearchParamsToFormData(searchParams);
	} else if (opts.body == null) {
		searchParams = new URLSearchParams();
		formData = new FormData();
	} else try {
		searchParams = new URLSearchParams(opts.body);
		formData = convertSearchParamsToFormData(searchParams);
	} catch (e) {
		return getInvalidBodyError();
	}
	let submission = {
		formMethod,
		formAction,
		formEncType: opts && opts.formEncType || "application/x-www-form-urlencoded",
		formData,
		json: void 0,
		text: void 0
	};
	if (isMutationMethod(submission.formMethod)) return {
		path,
		submission
	};
	let parsedPath = parsePath(path);
	if (isFetcher && parsedPath.search && hasNakedIndexQuery(parsedPath.search)) searchParams.append("index", "");
	parsedPath.search = "?" + searchParams;
	return {
		path: createPath(parsedPath),
		submission
	};
}
function getLoaderMatchesUntilBoundary(matches, boundaryId, includeBoundary) {
	if (includeBoundary === void 0) includeBoundary = false;
	let index = matches.findIndex((m) => m.route.id === boundaryId);
	if (index >= 0) return matches.slice(0, includeBoundary ? index + 1 : index);
	return matches;
}
function getMatchesToLoad(history, state, matches, submission, location, initialHydration, skipActionErrorRevalidation, isRevalidationRequired, cancelledDeferredRoutes, cancelledFetcherLoads, deletedFetchers, fetchLoadMatches, fetchRedirectIds, routesToUse, basename, pendingActionResult) {
	let actionResult = pendingActionResult ? isErrorResult(pendingActionResult[1]) ? pendingActionResult[1].error : pendingActionResult[1].data : void 0;
	let currentUrl = history.createURL(state.location);
	let nextUrl = history.createURL(location);
	let boundaryMatches = matches;
	if (initialHydration && state.errors) boundaryMatches = getLoaderMatchesUntilBoundary(matches, Object.keys(state.errors)[0], true);
	else if (pendingActionResult && isErrorResult(pendingActionResult[1])) boundaryMatches = getLoaderMatchesUntilBoundary(matches, pendingActionResult[0]);
	let actionStatus = pendingActionResult ? pendingActionResult[1].statusCode : void 0;
	let shouldSkipRevalidation = skipActionErrorRevalidation && actionStatus && actionStatus >= 400;
	let navigationMatches = boundaryMatches.filter((match, index) => {
		let { route } = match;
		if (route.lazy) return true;
		if (route.loader == null) return false;
		if (initialHydration) return shouldLoadRouteOnHydration(route, state.loaderData, state.errors);
		if (isNewLoader(state.loaderData, state.matches[index], match) || cancelledDeferredRoutes.some((id) => id === match.route.id)) return true;
		let currentRouteMatch = state.matches[index];
		let nextRouteMatch = match;
		return shouldRevalidateLoader(match, _extends$2({
			currentUrl,
			currentParams: currentRouteMatch.params,
			nextUrl,
			nextParams: nextRouteMatch.params
		}, submission, {
			actionResult,
			actionStatus,
			defaultShouldRevalidate: shouldSkipRevalidation ? false : isRevalidationRequired || currentUrl.pathname + currentUrl.search === nextUrl.pathname + nextUrl.search || currentUrl.search !== nextUrl.search || isNewRouteInstance(currentRouteMatch, nextRouteMatch)
		}));
	});
	let revalidatingFetchers = [];
	fetchLoadMatches.forEach((f, key) => {
		if (initialHydration || !matches.some((m) => m.route.id === f.routeId) || deletedFetchers.has(key)) return;
		let fetcherMatches = matchRoutes(routesToUse, f.path, basename);
		if (!fetcherMatches) {
			revalidatingFetchers.push({
				key,
				routeId: f.routeId,
				path: f.path,
				matches: null,
				match: null,
				controller: null
			});
			return;
		}
		let fetcher = state.fetchers.get(key);
		let fetcherMatch = getTargetMatch(fetcherMatches, f.path);
		let shouldRevalidate = false;
		if (fetchRedirectIds.has(key)) shouldRevalidate = false;
		else if (cancelledFetcherLoads.has(key)) {
			cancelledFetcherLoads.delete(key);
			shouldRevalidate = true;
		} else if (fetcher && fetcher.state !== "idle" && fetcher.data === void 0) shouldRevalidate = isRevalidationRequired;
		else shouldRevalidate = shouldRevalidateLoader(fetcherMatch, _extends$2({
			currentUrl,
			currentParams: state.matches[state.matches.length - 1].params,
			nextUrl,
			nextParams: matches[matches.length - 1].params
		}, submission, {
			actionResult,
			actionStatus,
			defaultShouldRevalidate: shouldSkipRevalidation ? false : isRevalidationRequired
		}));
		if (shouldRevalidate) revalidatingFetchers.push({
			key,
			routeId: f.routeId,
			path: f.path,
			matches: fetcherMatches,
			match: fetcherMatch,
			controller: new AbortController()
		});
	});
	return [navigationMatches, revalidatingFetchers];
}
function shouldLoadRouteOnHydration(route, loaderData, errors) {
	if (route.lazy) return true;
	if (!route.loader) return false;
	let hasData = loaderData != null && loaderData[route.id] !== void 0;
	let hasError = errors != null && errors[route.id] !== void 0;
	if (!hasData && hasError) return false;
	if (typeof route.loader === "function" && route.loader.hydrate === true) return true;
	return !hasData && !hasError;
}
function isNewLoader(currentLoaderData, currentMatch, match) {
	let isNew = !currentMatch || match.route.id !== currentMatch.route.id;
	let isMissingData = currentLoaderData[match.route.id] === void 0;
	return isNew || isMissingData;
}
function isNewRouteInstance(currentMatch, match) {
	let currentPath = currentMatch.route.path;
	return currentMatch.pathname !== match.pathname || currentPath != null && currentPath.endsWith("*") && currentMatch.params["*"] !== match.params["*"];
}
function shouldRevalidateLoader(loaderMatch, arg) {
	if (loaderMatch.route.shouldRevalidate) {
		let routeChoice = loaderMatch.route.shouldRevalidate(arg);
		if (typeof routeChoice === "boolean") return routeChoice;
	}
	return arg.defaultShouldRevalidate;
}
function patchRoutesImpl(routeId, children, routesToUse, manifest, mapRouteProperties) {
	var _childrenToPatch;
	let childrenToPatch;
	if (routeId) {
		let route = manifest[routeId];
		invariant(route, "No route found to patch children into: routeId = " + routeId);
		if (!route.children) route.children = [];
		childrenToPatch = route.children;
	} else childrenToPatch = routesToUse;
	let newRoutes = convertRoutesToDataRoutes(children.filter((newRoute) => !childrenToPatch.some((existingRoute) => isSameRoute(newRoute, existingRoute))), mapRouteProperties, [
		routeId || "_",
		"patch",
		String(((_childrenToPatch = childrenToPatch) == null ? void 0 : _childrenToPatch.length) || "0")
	], manifest);
	childrenToPatch.push(...newRoutes);
}
function isSameRoute(newRoute, existingRoute) {
	if ("id" in newRoute && "id" in existingRoute && newRoute.id === existingRoute.id) return true;
	if (!(newRoute.index === existingRoute.index && newRoute.path === existingRoute.path && newRoute.caseSensitive === existingRoute.caseSensitive)) return false;
	if ((!newRoute.children || newRoute.children.length === 0) && (!existingRoute.children || existingRoute.children.length === 0)) return true;
	return newRoute.children.every((aChild, i) => {
		var _existingRoute$childr;
		return (_existingRoute$childr = existingRoute.children) == null ? void 0 : _existingRoute$childr.some((bChild) => isSameRoute(aChild, bChild));
	});
}
/**
* Execute route.lazy() methods to lazily load route modules (loader, action,
* shouldRevalidate) and update the routeManifest in place which shares objects
* with dataRoutes so those get updated as well.
*/
async function loadLazyRouteModule(route, mapRouteProperties, manifest) {
	if (!route.lazy) return;
	let lazyRoute = await route.lazy();
	if (!route.lazy) return;
	let routeToUpdate = manifest[route.id];
	invariant(routeToUpdate, "No route found in manifest");
	let routeUpdates = {};
	for (let lazyRouteProperty in lazyRoute) {
		let isPropertyStaticallyDefined = routeToUpdate[lazyRouteProperty] !== void 0 && lazyRouteProperty !== "hasErrorBoundary";
		warning(!isPropertyStaticallyDefined, "Route \"" + routeToUpdate.id + "\" has a static property \"" + lazyRouteProperty + "\" defined but its lazy function is also returning a value for this property. " + ("The lazy route property \"" + lazyRouteProperty + "\" will be ignored."));
		if (!isPropertyStaticallyDefined && !immutableRouteKeys.has(lazyRouteProperty)) routeUpdates[lazyRouteProperty] = lazyRoute[lazyRouteProperty];
	}
	Object.assign(routeToUpdate, routeUpdates);
	Object.assign(routeToUpdate, _extends$2({}, mapRouteProperties(routeToUpdate), { lazy: void 0 }));
}
async function defaultDataStrategy(_ref4) {
	let { matches } = _ref4;
	let matchesToLoad = matches.filter((m) => m.shouldLoad);
	return (await Promise.all(matchesToLoad.map((m) => m.resolve()))).reduce((acc, result, i) => Object.assign(acc, { [matchesToLoad[i].route.id]: result }), {});
}
async function callDataStrategyImpl(dataStrategyImpl, type, state, request, matchesToLoad, matches, fetcherKey, manifest, mapRouteProperties, requestContext) {
	let loadRouteDefinitionsPromises = matches.map((m) => m.route.lazy ? loadLazyRouteModule(m.route, mapRouteProperties, manifest) : void 0);
	let results = await dataStrategyImpl({
		matches: matches.map((match, i) => {
			let loadRoutePromise = loadRouteDefinitionsPromises[i];
			let shouldLoad = matchesToLoad.some((m) => m.route.id === match.route.id);
			let resolve = async (handlerOverride) => {
				if (handlerOverride && request.method === "GET" && (match.route.lazy || match.route.loader)) shouldLoad = true;
				return shouldLoad ? callLoaderOrAction(type, request, match, loadRoutePromise, handlerOverride, requestContext) : Promise.resolve({
					type: ResultType.data,
					result: void 0
				});
			};
			return _extends$2({}, match, {
				shouldLoad,
				resolve
			});
		}),
		request,
		params: matches[0].params,
		fetcherKey,
		context: requestContext
	});
	try {
		await Promise.all(loadRouteDefinitionsPromises);
	} catch (e) {}
	return results;
}
async function callLoaderOrAction(type, request, match, loadRoutePromise, handlerOverride, staticContext) {
	let result;
	let onReject;
	let runHandler = (handler) => {
		let reject;
		let abortPromise = new Promise((_, r) => reject = r);
		onReject = () => reject();
		request.signal.addEventListener("abort", onReject);
		let actualHandler = (ctx) => {
			if (typeof handler !== "function") return Promise.reject(/* @__PURE__ */ new Error("You cannot call the handler for a route which defines a boolean " + ("\"" + type + "\" [routeId: " + match.route.id + "]")));
			return handler({
				request,
				params: match.params,
				context: staticContext
			}, ...ctx !== void 0 ? [ctx] : []);
		};
		let handlerPromise = (async () => {
			try {
				return {
					type: "data",
					result: await (handlerOverride ? handlerOverride((ctx) => actualHandler(ctx)) : actualHandler())
				};
			} catch (e) {
				return {
					type: "error",
					result: e
				};
			}
		})();
		return Promise.race([handlerPromise, abortPromise]);
	};
	try {
		let handler = match.route[type];
		if (loadRoutePromise) if (handler) {
			let handlerError;
			let [value] = await Promise.all([runHandler(handler).catch((e) => {
				handlerError = e;
			}), loadRoutePromise]);
			if (handlerError !== void 0) throw handlerError;
			result = value;
		} else {
			await loadRoutePromise;
			handler = match.route[type];
			if (handler) result = await runHandler(handler);
			else if (type === "action") {
				let url = new URL(request.url);
				let pathname = url.pathname + url.search;
				throw getInternalRouterError(405, {
					method: request.method,
					pathname,
					routeId: match.route.id
				});
			} else return {
				type: ResultType.data,
				result: void 0
			};
		}
		else if (!handler) {
			let url = new URL(request.url);
			throw getInternalRouterError(404, { pathname: url.pathname + url.search });
		} else result = await runHandler(handler);
		invariant(result.result !== void 0, "You defined " + (type === "action" ? "an action" : "a loader") + " for route " + ("\"" + match.route.id + "\" but didn't return anything from your `" + type + "` ") + "function. Please return a value or `null`.");
	} catch (e) {
		return {
			type: ResultType.error,
			result: e
		};
	} finally {
		if (onReject) request.signal.removeEventListener("abort", onReject);
	}
	return result;
}
async function convertDataStrategyResultToDataResult(dataStrategyResult) {
	let { result, type } = dataStrategyResult;
	if (isResponse(result)) {
		let data;
		try {
			let contentType = result.headers.get("Content-Type");
			if (contentType && /\bapplication\/json\b/.test(contentType)) if (result.body == null) data = null;
			else data = await result.json();
			else data = await result.text();
		} catch (e) {
			return {
				type: ResultType.error,
				error: e
			};
		}
		if (type === ResultType.error) return {
			type: ResultType.error,
			error: new ErrorResponseImpl(result.status, result.statusText, data),
			statusCode: result.status,
			headers: result.headers
		};
		return {
			type: ResultType.data,
			data,
			statusCode: result.status,
			headers: result.headers
		};
	}
	if (type === ResultType.error) {
		if (isDataWithResponseInit(result)) {
			var _result$init3, _result$init4;
			if (result.data instanceof Error) {
				var _result$init, _result$init2;
				return {
					type: ResultType.error,
					error: result.data,
					statusCode: (_result$init = result.init) == null ? void 0 : _result$init.status,
					headers: (_result$init2 = result.init) != null && _result$init2.headers ? new Headers(result.init.headers) : void 0
				};
			}
			return {
				type: ResultType.error,
				error: new ErrorResponseImpl(((_result$init3 = result.init) == null ? void 0 : _result$init3.status) || 500, void 0, result.data),
				statusCode: isRouteErrorResponse(result) ? result.status : void 0,
				headers: (_result$init4 = result.init) != null && _result$init4.headers ? new Headers(result.init.headers) : void 0
			};
		}
		return {
			type: ResultType.error,
			error: result,
			statusCode: isRouteErrorResponse(result) ? result.status : void 0
		};
	}
	if (isDeferredData(result)) {
		var _result$init5, _result$init6;
		return {
			type: ResultType.deferred,
			deferredData: result,
			statusCode: (_result$init5 = result.init) == null ? void 0 : _result$init5.status,
			headers: ((_result$init6 = result.init) == null ? void 0 : _result$init6.headers) && new Headers(result.init.headers)
		};
	}
	if (isDataWithResponseInit(result)) {
		var _result$init7, _result$init8;
		return {
			type: ResultType.data,
			data: result.data,
			statusCode: (_result$init7 = result.init) == null ? void 0 : _result$init7.status,
			headers: (_result$init8 = result.init) != null && _result$init8.headers ? new Headers(result.init.headers) : void 0
		};
	}
	return {
		type: ResultType.data,
		data: result
	};
}
function normalizeRelativeRoutingRedirectResponse(response, request, routeId, matches, basename, v7_relativeSplatPath) {
	let location = response.headers.get("Location");
	invariant(location, "Redirects returned/thrown from loaders/actions must have a Location header");
	if (!ABSOLUTE_URL_REGEX$2.test(location)) {
		let trimmedMatches = matches.slice(0, matches.findIndex((m) => m.route.id === routeId) + 1);
		location = normalizeTo(new URL(request.url), trimmedMatches, basename, true, location, v7_relativeSplatPath);
		response.headers.set("Location", location);
	}
	return response;
}
function normalizeRedirectLocation(location, currentUrl, basename, historyInstance) {
	let invalidProtocols = [
		"about:",
		"blob:",
		"chrome:",
		"chrome-untrusted:",
		"content:",
		"data:",
		"devtools:",
		"file:",
		"filesystem:",
		"javascript:"
	];
	if (ABSOLUTE_URL_REGEX$2.test(location)) {
		let normalizedLocation = location;
		let url = normalizedLocation.startsWith("//") ? new URL(currentUrl.protocol + normalizedLocation) : new URL(normalizedLocation);
		if (invalidProtocols.includes(url.protocol)) throw new Error("Invalid redirect location");
		let isSameBasename = stripBasename(url.pathname, basename) != null;
		if (url.origin === currentUrl.origin && isSameBasename) return removeDoubleSlashes(url.pathname) + url.search + url.hash;
	}
	try {
		let url = historyInstance.createURL(location);
		if (invalidProtocols.includes(url.protocol)) throw new Error("Invalid redirect location");
	} catch (e) {}
	return location;
}
function createClientSideRequest(history, location, signal, submission) {
	let url = history.createURL(stripHashFromPath(location)).toString();
	let init = { signal };
	if (submission && isMutationMethod(submission.formMethod)) {
		let { formMethod, formEncType } = submission;
		init.method = formMethod.toUpperCase();
		if (formEncType === "application/json") {
			init.headers = new Headers({ "Content-Type": formEncType });
			init.body = JSON.stringify(submission.json);
		} else if (formEncType === "text/plain") init.body = submission.text;
		else if (formEncType === "application/x-www-form-urlencoded" && submission.formData) init.body = convertFormDataToSearchParams(submission.formData);
		else init.body = submission.formData;
	}
	return new Request(url, init);
}
function convertFormDataToSearchParams(formData) {
	let searchParams = new URLSearchParams();
	for (let [key, value] of formData.entries()) searchParams.append(key, typeof value === "string" ? value : value.name);
	return searchParams;
}
function convertSearchParamsToFormData(searchParams) {
	let formData = new FormData();
	for (let [key, value] of searchParams.entries()) formData.append(key, value);
	return formData;
}
function processRouteLoaderData(matches, results, pendingActionResult, activeDeferreds, skipLoaderErrorBubbling) {
	let loaderData = {};
	let errors = null;
	let statusCode;
	let foundError = false;
	let loaderHeaders = {};
	let pendingError = pendingActionResult && isErrorResult(pendingActionResult[1]) ? pendingActionResult[1].error : void 0;
	matches.forEach((match) => {
		if (!(match.route.id in results)) return;
		let id = match.route.id;
		let result = results[id];
		invariant(!isRedirectResult(result), "Cannot handle redirect results in processLoaderData");
		if (isErrorResult(result)) {
			let error = result.error;
			if (pendingError !== void 0) {
				error = pendingError;
				pendingError = void 0;
			}
			errors = errors || {};
			if (skipLoaderErrorBubbling) errors[id] = error;
			else {
				let boundaryMatch = findNearestBoundary(matches, id);
				if (errors[boundaryMatch.route.id] == null) errors[boundaryMatch.route.id] = error;
			}
			loaderData[id] = void 0;
			if (!foundError) {
				foundError = true;
				statusCode = isRouteErrorResponse(result.error) ? result.error.status : 500;
			}
			if (result.headers) loaderHeaders[id] = result.headers;
		} else if (isDeferredResult(result)) {
			activeDeferreds.set(id, result.deferredData);
			loaderData[id] = result.deferredData.data;
			if (result.statusCode != null && result.statusCode !== 200 && !foundError) statusCode = result.statusCode;
			if (result.headers) loaderHeaders[id] = result.headers;
		} else {
			loaderData[id] = result.data;
			if (result.statusCode && result.statusCode !== 200 && !foundError) statusCode = result.statusCode;
			if (result.headers) loaderHeaders[id] = result.headers;
		}
	});
	if (pendingError !== void 0 && pendingActionResult) {
		errors = { [pendingActionResult[0]]: pendingError };
		loaderData[pendingActionResult[0]] = void 0;
	}
	return {
		loaderData,
		errors,
		statusCode: statusCode || 200,
		loaderHeaders
	};
}
function processLoaderData(state, matches, results, pendingActionResult, revalidatingFetchers, fetcherResults, activeDeferreds) {
	let { loaderData, errors } = processRouteLoaderData(matches, results, pendingActionResult, activeDeferreds, false);
	revalidatingFetchers.forEach((rf) => {
		let { key, match, controller } = rf;
		let result = fetcherResults[key];
		invariant(result, "Did not find corresponding fetcher result");
		if (controller && controller.signal.aborted) return;
		else if (isErrorResult(result)) {
			let boundaryMatch = findNearestBoundary(state.matches, match == null ? void 0 : match.route.id);
			if (!(errors && errors[boundaryMatch.route.id])) errors = _extends$2({}, errors, { [boundaryMatch.route.id]: result.error });
			state.fetchers.delete(key);
		} else if (isRedirectResult(result)) invariant(false, "Unhandled fetcher revalidation redirect");
		else if (isDeferredResult(result)) invariant(false, "Unhandled fetcher deferred data");
		else {
			let doneFetcher = getDoneFetcher(result.data);
			state.fetchers.set(key, doneFetcher);
		}
	});
	return {
		loaderData,
		errors
	};
}
function mergeLoaderData(loaderData, newLoaderData, matches, errors) {
	let mergedLoaderData = _extends$2({}, newLoaderData);
	for (let match of matches) {
		let id = match.route.id;
		if (newLoaderData.hasOwnProperty(id)) {
			if (newLoaderData[id] !== void 0) mergedLoaderData[id] = newLoaderData[id];
		} else if (loaderData[id] !== void 0 && match.route.loader) mergedLoaderData[id] = loaderData[id];
		if (errors && errors.hasOwnProperty(id)) break;
	}
	return mergedLoaderData;
}
function getActionDataForCommit(pendingActionResult) {
	if (!pendingActionResult) return {};
	return isErrorResult(pendingActionResult[1]) ? { actionData: {} } : { actionData: { [pendingActionResult[0]]: pendingActionResult[1].data } };
}
function findNearestBoundary(matches, routeId) {
	return (routeId ? matches.slice(0, matches.findIndex((m) => m.route.id === routeId) + 1) : [...matches]).reverse().find((m) => m.route.hasErrorBoundary === true) || matches[0];
}
function getShortCircuitMatches(routes) {
	let route = routes.length === 1 ? routes[0] : routes.find((r) => r.index || !r.path || r.path === "/") || { id: "__shim-error-route__" };
	return {
		matches: [{
			params: {},
			pathname: "",
			pathnameBase: "",
			route
		}],
		route
	};
}
function getInternalRouterError(status, _temp5) {
	let { pathname, routeId, method, type, message } = _temp5 === void 0 ? {} : _temp5;
	let statusText = "Unknown Server Error";
	let errorMessage = "Unknown @remix-run/router error";
	if (status === 400) {
		statusText = "Bad Request";
		if (method && pathname && routeId) errorMessage = "You made a " + method + " request to \"" + pathname + "\" but " + ("did not provide a `loader` for route \"" + routeId + "\", ") + "so there is no way to handle the request.";
		else if (type === "defer-action") errorMessage = "defer() is not supported in actions";
		else if (type === "invalid-body") errorMessage = "Unable to encode submission body";
	} else if (status === 403) {
		statusText = "Forbidden";
		errorMessage = "Route \"" + routeId + "\" does not match URL \"" + pathname + "\"";
	} else if (status === 404) {
		statusText = "Not Found";
		errorMessage = "No route matches URL \"" + pathname + "\"";
	} else if (status === 405) {
		statusText = "Method Not Allowed";
		if (method && pathname && routeId) errorMessage = "You made a " + method.toUpperCase() + " request to \"" + pathname + "\" but " + ("did not provide an `action` for route \"" + routeId + "\", ") + "so there is no way to handle the request.";
		else if (method) errorMessage = "Invalid request method \"" + method.toUpperCase() + "\"";
	}
	return new ErrorResponseImpl(status || 500, statusText, new Error(errorMessage), true);
}
function findRedirect(results) {
	let entries = Object.entries(results);
	for (let i = entries.length - 1; i >= 0; i--) {
		let [key, result] = entries[i];
		if (isRedirectResult(result)) return {
			key,
			result
		};
	}
}
function stripHashFromPath(path) {
	let parsedPath = typeof path === "string" ? parsePath(path) : path;
	return createPath(_extends$2({}, parsedPath, { hash: "" }));
}
function isHashChangeOnly(a, b) {
	if (a.pathname !== b.pathname || a.search !== b.search) return false;
	if (a.hash === "") return b.hash !== "";
	else if (a.hash === b.hash) return true;
	else if (b.hash !== "") return true;
	return false;
}
function isRedirectDataStrategyResultResult(result) {
	return isResponse(result.result) && redirectStatusCodes.has(result.result.status);
}
function isDeferredResult(result) {
	return result.type === ResultType.deferred;
}
function isErrorResult(result) {
	return result.type === ResultType.error;
}
function isRedirectResult(result) {
	return (result && result.type) === ResultType.redirect;
}
function isDataWithResponseInit(value) {
	return typeof value === "object" && value != null && "type" in value && "data" in value && "init" in value && value.type === "DataWithResponseInit";
}
function isDeferredData(value) {
	let deferred = value;
	return deferred && typeof deferred === "object" && typeof deferred.data === "object" && typeof deferred.subscribe === "function" && typeof deferred.cancel === "function" && typeof deferred.resolveData === "function";
}
function isResponse(value) {
	return value != null && typeof value.status === "number" && typeof value.statusText === "string" && typeof value.headers === "object" && typeof value.body !== "undefined";
}
function isValidMethod(method) {
	return validRequestMethods.has(method.toLowerCase());
}
function isMutationMethod(method) {
	return validMutationMethods.has(method.toLowerCase());
}
async function resolveNavigationDeferredResults(matches, results, signal, currentMatches, currentLoaderData) {
	let entries = Object.entries(results);
	for (let index = 0; index < entries.length; index++) {
		let [routeId, result] = entries[index];
		let match = matches.find((m) => (m == null ? void 0 : m.route.id) === routeId);
		if (!match) continue;
		let currentMatch = currentMatches.find((m) => m.route.id === match.route.id);
		let isRevalidatingLoader = currentMatch != null && !isNewRouteInstance(currentMatch, match) && (currentLoaderData && currentLoaderData[match.route.id]) !== void 0;
		if (isDeferredResult(result) && isRevalidatingLoader) await resolveDeferredData(result, signal, false).then((result) => {
			if (result) results[routeId] = result;
		});
	}
}
async function resolveFetcherDeferredResults(matches, results, revalidatingFetchers) {
	for (let index = 0; index < revalidatingFetchers.length; index++) {
		let { key, routeId, controller } = revalidatingFetchers[index];
		let result = results[key];
		if (!matches.find((m) => (m == null ? void 0 : m.route.id) === routeId)) continue;
		if (isDeferredResult(result)) {
			invariant(controller, "Expected an AbortController for revalidating fetcher deferred result");
			await resolveDeferredData(result, controller.signal, true).then((result) => {
				if (result) results[key] = result;
			});
		}
	}
}
async function resolveDeferredData(result, signal, unwrap) {
	if (unwrap === void 0) unwrap = false;
	if (await result.deferredData.resolveData(signal)) return;
	if (unwrap) try {
		return {
			type: ResultType.data,
			data: result.deferredData.unwrappedData
		};
	} catch (e) {
		return {
			type: ResultType.error,
			error: e
		};
	}
	return {
		type: ResultType.data,
		data: result.deferredData.data
	};
}
function hasNakedIndexQuery(search) {
	return new URLSearchParams(search).getAll("index").some((v) => v === "");
}
function getTargetMatch(matches, location) {
	let search = typeof location === "string" ? parsePath(location).search : location.search;
	if (matches[matches.length - 1].route.index && hasNakedIndexQuery(search || "")) return matches[matches.length - 1];
	let pathMatches = getPathContributingMatches(matches);
	return pathMatches[pathMatches.length - 1];
}
function getSubmissionFromNavigation(navigation) {
	let { formMethod, formAction, formEncType, text, formData, json } = navigation;
	if (!formMethod || !formAction || !formEncType) return;
	if (text != null) return {
		formMethod,
		formAction,
		formEncType,
		formData: void 0,
		json: void 0,
		text
	};
	else if (formData != null) return {
		formMethod,
		formAction,
		formEncType,
		formData,
		json: void 0,
		text: void 0
	};
	else if (json !== void 0) return {
		formMethod,
		formAction,
		formEncType,
		formData: void 0,
		json,
		text: void 0
	};
}
function getLoadingNavigation(location, submission) {
	if (submission) return {
		state: "loading",
		location,
		formMethod: submission.formMethod,
		formAction: submission.formAction,
		formEncType: submission.formEncType,
		formData: submission.formData,
		json: submission.json,
		text: submission.text
	};
	else return {
		state: "loading",
		location,
		formMethod: void 0,
		formAction: void 0,
		formEncType: void 0,
		formData: void 0,
		json: void 0,
		text: void 0
	};
}
function getSubmittingNavigation(location, submission) {
	return {
		state: "submitting",
		location,
		formMethod: submission.formMethod,
		formAction: submission.formAction,
		formEncType: submission.formEncType,
		formData: submission.formData,
		json: submission.json,
		text: submission.text
	};
}
function getLoadingFetcher(submission, data) {
	if (submission) return {
		state: "loading",
		formMethod: submission.formMethod,
		formAction: submission.formAction,
		formEncType: submission.formEncType,
		formData: submission.formData,
		json: submission.json,
		text: submission.text,
		data
	};
	else return {
		state: "loading",
		formMethod: void 0,
		formAction: void 0,
		formEncType: void 0,
		formData: void 0,
		json: void 0,
		text: void 0,
		data
	};
}
function getSubmittingFetcher(submission, existingFetcher) {
	return {
		state: "submitting",
		formMethod: submission.formMethod,
		formAction: submission.formAction,
		formEncType: submission.formEncType,
		formData: submission.formData,
		json: submission.json,
		text: submission.text,
		data: existingFetcher ? existingFetcher.data : void 0
	};
}
function getDoneFetcher(data) {
	return {
		state: "idle",
		formMethod: void 0,
		formAction: void 0,
		formEncType: void 0,
		formData: void 0,
		json: void 0,
		text: void 0,
		data
	};
}
function restoreAppliedTransitions(_window, transitions) {
	try {
		let sessionPositions = _window.sessionStorage.getItem(TRANSITIONS_STORAGE_KEY);
		if (sessionPositions) {
			let json = JSON.parse(sessionPositions);
			for (let [k, v] of Object.entries(json || {})) if (v && Array.isArray(v)) transitions.set(k, new Set(v || []));
		}
	} catch (e) {}
}
function persistAppliedTransitions(_window, transitions) {
	if (transitions.size > 0) {
		let json = {};
		for (let [k, v] of transitions) json[k] = [...v];
		try {
			_window.sessionStorage.setItem(TRANSITIONS_STORAGE_KEY, JSON.stringify(json));
		} catch (error) {
			warning(false, "Failed to save applied view transitions in sessionStorage (" + error + ").");
		}
	}
}
//#endregion
//#region node_modules/react-router/dist/index.js
/**
* React Router v6.30.4
*
* Copyright (c) Remix Software Inc.
*
* This source code is licensed under the MIT license found in the
* LICENSE.md file in the root directory of this source tree.
*
* @license MIT
*/
function _extends$1() {
	return _extends$1 = Object.assign ? Object.assign.bind() : function(n) {
		for (var e = 1; e < arguments.length; e++) {
			var t = arguments[e];
			for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
		}
		return n;
	}, _extends$1.apply(null, arguments);
}
var DataRouterContext = /*#__PURE__*/ import_react.createContext(null);
DataRouterContext.displayName = "DataRouter";
var DataRouterStateContext = /*#__PURE__*/ import_react.createContext(null);
DataRouterStateContext.displayName = "DataRouterState";
var AwaitContext = /*#__PURE__*/ import_react.createContext(null);
AwaitContext.displayName = "Await";
/**
* A Navigator is a "location changer"; it's how you get to different locations.
*
* Every history instance conforms to the Navigator interface, but the
* distinction is useful primarily when it comes to the low-level `<Router>` API
* where both the location and a navigator must be provided separately in order
* to avoid "tearing" that may occur in a suspense-enabled app if the action
* and/or location were to be read directly from the history instance.
*/
var NavigationContext = /*#__PURE__*/ import_react.createContext(null);
NavigationContext.displayName = "Navigation";
var LocationContext = /*#__PURE__*/ import_react.createContext(null);
LocationContext.displayName = "Location";
var RouteContext = /*#__PURE__*/ import_react.createContext({
	outlet: null,
	matches: [],
	isDataRoute: false
});
RouteContext.displayName = "Route";
var RouteErrorContext = /*#__PURE__*/ import_react.createContext(null);
RouteErrorContext.displayName = "RouteError";
/**
* Returns the full href for the given "to" value. This is useful for building
* custom links that are also accessible and preserve right-click behavior.
*
* @see https://reactrouter.com/v6/hooks/use-href
*/
function useHref(to, _temp) {
	let { relative } = _temp === void 0 ? {} : _temp;
	!useInRouterContext() && invariant(false, "useHref() may be used only in the context of a <Router> component.");
	let { basename, navigator } = import_react.useContext(NavigationContext);
	let { hash, pathname, search } = useResolvedPath(to, { relative });
	let joinedPathname = pathname;
	if (basename !== "/") joinedPathname = pathname === "/" ? basename : joinPaths([basename, pathname]);
	return navigator.createHref({
		pathname: joinedPathname,
		search,
		hash
	});
}
/**
* Returns true if this component is a descendant of a `<Router>`.
*
* @see https://reactrouter.com/v6/hooks/use-in-router-context
*/
function useInRouterContext() {
	return import_react.useContext(LocationContext) != null;
}
/**
* Returns the current location object, which represents the current URL in web
* browsers.
*
* Note: If you're using this it may mean you're doing some of your own
* "routing" in your app, and we'd like to know what your use case is. We may
* be able to provide something higher-level to better suit your needs.
*
* @see https://reactrouter.com/v6/hooks/use-location
*/
function useLocation() {
	!useInRouterContext() && invariant(false, "useLocation() may be used only in the context of a <Router> component.");
	return import_react.useContext(LocationContext).location;
}
/**
* Returns the current navigation action which describes how the router came to
* the current location, either by a pop, push, or replace on the history stack.
*
* @see https://reactrouter.com/v6/hooks/use-navigation-type
*/
function useNavigationType() {
	return import_react.useContext(LocationContext).navigationType;
}
/**
* Returns a PathMatch object if the given pattern matches the current URL.
* This is useful for components that need to know "active" state, e.g.
* `<NavLink>`.
*
* @see https://reactrouter.com/v6/hooks/use-match
*/
function useMatch(pattern) {
	!useInRouterContext() && invariant(false, "useMatch() may be used only in the context of a <Router> component.");
	let { pathname } = useLocation();
	return import_react.useMemo(() => matchPath(pattern, decodePath(pathname)), [pathname, pattern]);
}
/**
* The interface for the navigate() function returned from useNavigate().
*/
var navigateEffectWarning = "You should call navigate() in a React.useEffect(), not when your component is first rendered.";
function useIsomorphicLayoutEffect(cb) {
	if (!import_react.useContext(NavigationContext).static) import_react.useLayoutEffect(cb);
}
/**
* Returns an imperative method for changing the location. Used by `<Link>`s, but
* may also be used by other elements to change the location.
*
* @see https://reactrouter.com/v6/hooks/use-navigate
*/
function useNavigate() {
	let { isDataRoute } = import_react.useContext(RouteContext);
	return isDataRoute ? useNavigateStable() : useNavigateUnstable();
}
function useNavigateUnstable() {
	!useInRouterContext() && invariant(false, "useNavigate() may be used only in the context of a <Router> component.");
	let dataRouterContext = import_react.useContext(DataRouterContext);
	let { basename, future, navigator } = import_react.useContext(NavigationContext);
	let { matches } = import_react.useContext(RouteContext);
	let { pathname: locationPathname } = useLocation();
	let routePathnamesJson = JSON.stringify(getResolveToMatches(matches, future.v7_relativeSplatPath));
	let activeRef = import_react.useRef(false);
	useIsomorphicLayoutEffect(() => {
		activeRef.current = true;
	});
	return import_react.useCallback(function(to, options) {
		if (options === void 0) options = {};
		warning(activeRef.current, navigateEffectWarning);
		if (!activeRef.current) return;
		if (typeof to === "number") {
			navigator.go(to);
			return;
		}
		let path = resolveTo(to, JSON.parse(routePathnamesJson), locationPathname, options.relative === "path");
		if (dataRouterContext == null && basename !== "/") path.pathname = path.pathname === "/" ? basename : joinPaths([basename, path.pathname]);
		(!!options.replace ? navigator.replace : navigator.push)(path, options.state, options);
	}, [
		basename,
		navigator,
		routePathnamesJson,
		locationPathname,
		dataRouterContext
	]);
}
var OutletContext = /*#__PURE__*/ import_react.createContext(null);
/**
* Returns the context (if provided) for the child route at this level of the route
* hierarchy.
* @see https://reactrouter.com/v6/hooks/use-outlet-context
*/
function useOutletContext() {
	return import_react.useContext(OutletContext);
}
/**
* Returns the element for the child route at this level of the route
* hierarchy. Used internally by `<Outlet>` to render child routes.
*
* @see https://reactrouter.com/v6/hooks/use-outlet
*/
function useOutlet(context) {
	let outlet = import_react.useContext(RouteContext).outlet;
	if (outlet) return /*#__PURE__*/ import_react.createElement(OutletContext.Provider, { value: context }, outlet);
	return outlet;
}
/**
* Returns an object of key/value pairs of the dynamic params from the current
* URL that were matched by the route path.
*
* @see https://reactrouter.com/v6/hooks/use-params
*/
function useParams() {
	let { matches } = import_react.useContext(RouteContext);
	let routeMatch = matches[matches.length - 1];
	return routeMatch ? routeMatch.params : {};
}
/**
* Resolves the pathname of the given `to` value against the current location.
*
* @see https://reactrouter.com/v6/hooks/use-resolved-path
*/
function useResolvedPath(to, _temp2) {
	let { relative } = _temp2 === void 0 ? {} : _temp2;
	let { future } = import_react.useContext(NavigationContext);
	let { matches } = import_react.useContext(RouteContext);
	let { pathname: locationPathname } = useLocation();
	let routePathnamesJson = JSON.stringify(getResolveToMatches(matches, future.v7_relativeSplatPath));
	return import_react.useMemo(() => resolveTo(to, JSON.parse(routePathnamesJson), locationPathname, relative === "path"), [
		to,
		routePathnamesJson,
		locationPathname,
		relative
	]);
}
/**
* Returns the element of the route that matched the current location, prepared
* with the correct context to render the remainder of the route tree. Route
* elements in the tree must render an `<Outlet>` to render their child route's
* element.
*
* @see https://reactrouter.com/v6/hooks/use-routes
*/
function useRoutes(routes, locationArg) {
	return useRoutesImpl(routes, locationArg);
}
function useRoutesImpl(routes, locationArg, dataRouterState, future) {
	!useInRouterContext() && invariant(false, "useRoutes() may be used only in the context of a <Router> component.");
	let { navigator } = import_react.useContext(NavigationContext);
	let { matches: parentMatches } = import_react.useContext(RouteContext);
	let routeMatch = parentMatches[parentMatches.length - 1];
	let parentParams = routeMatch ? routeMatch.params : {};
	let parentPathname = routeMatch ? routeMatch.pathname : "/";
	let parentPathnameBase = routeMatch ? routeMatch.pathnameBase : "/";
	let parentRoute = routeMatch && routeMatch.route;
	{
		let parentPath = parentRoute && parentRoute.path || "";
		warningOnce(parentPathname, !parentRoute || parentPath.endsWith("*"), "You rendered descendant <Routes> (or called `useRoutes()`) at " + ("\"" + parentPathname + "\" (under <Route path=\"" + parentPath + "\">) but the ") + "parent route path has no trailing \"*\". This means if you navigate deeper, the parent won't match anymore and therefore the child routes will never render.\n\n" + ("Please change the parent <Route path=\"" + parentPath + "\"> to <Route ") + ("path=\"" + (parentPath === "/" ? "*" : parentPath + "/*") + "\">."));
	}
	let locationFromContext = useLocation();
	let location;
	if (locationArg) {
		var _parsedLocationArg$pa;
		let parsedLocationArg = typeof locationArg === "string" ? parsePath(locationArg) : locationArg;
		!(parentPathnameBase === "/" || ((_parsedLocationArg$pa = parsedLocationArg.pathname) == null ? void 0 : _parsedLocationArg$pa.startsWith(parentPathnameBase))) && invariant(false, "When overriding the location using `<Routes location>` or `useRoutes(routes, location)`, the location pathname must begin with the portion of the URL pathname that was " + ("matched by all parent routes. The current pathname base is \"" + parentPathnameBase + "\" ") + ("but pathname \"" + parsedLocationArg.pathname + "\" was given in the `location` prop."));
		location = parsedLocationArg;
	} else location = locationFromContext;
	let pathname = location.pathname || "/";
	let remainingPathname = pathname;
	if (parentPathnameBase !== "/") {
		let parentSegments = parentPathnameBase.replace(/^\//, "").split("/");
		remainingPathname = "/" + pathname.replace(/^\//, "").split("/").slice(parentSegments.length).join("/");
	}
	let matches = matchRoutes(routes, { pathname: remainingPathname });
	warning(parentRoute || matches != null, "No routes matched location \"" + location.pathname + location.search + location.hash + "\" ");
	warning(matches == null || matches[matches.length - 1].route.element !== void 0 || matches[matches.length - 1].route.Component !== void 0 || matches[matches.length - 1].route.lazy !== void 0, "Matched leaf route at location \"" + location.pathname + location.search + location.hash + "\" does not have an element or Component. This means it will render an <Outlet /> with a null value by default resulting in an \"empty\" page.");
	let renderedMatches = _renderMatches(matches && matches.map((match) => Object.assign({}, match, {
		params: Object.assign({}, parentParams, match.params),
		pathname: joinPaths([parentPathnameBase, navigator.encodeLocation ? navigator.encodeLocation(match.pathname).pathname : match.pathname]),
		pathnameBase: match.pathnameBase === "/" ? parentPathnameBase : joinPaths([parentPathnameBase, navigator.encodeLocation ? navigator.encodeLocation(match.pathnameBase).pathname : match.pathnameBase])
	})), parentMatches, dataRouterState, future);
	if (locationArg && renderedMatches) return /*#__PURE__*/ import_react.createElement(LocationContext.Provider, { value: {
		location: _extends$1({
			pathname: "/",
			search: "",
			hash: "",
			state: null,
			key: "default"
		}, location),
		navigationType: Action.Pop
	} }, renderedMatches);
	return renderedMatches;
}
function DefaultErrorComponent() {
	let error = useRouteError();
	let message = isRouteErrorResponse(error) ? error.status + " " + error.statusText : error instanceof Error ? error.message : JSON.stringify(error);
	let stack = error instanceof Error ? error.stack : null;
	let lightgrey = "rgba(200,200,200, 0.5)";
	let preStyles = {
		padding: "0.5rem",
		backgroundColor: lightgrey
	};
	let codeStyles = {
		padding: "2px 4px",
		backgroundColor: lightgrey
	};
	let devInfo = null;
	console.error("Error handled by React Router default ErrorBoundary:", error);
	devInfo = /*#__PURE__*/ import_react.createElement(import_react.Fragment, null, /*#__PURE__*/ import_react.createElement("p", null, "💿 Hey developer 👋"), /*#__PURE__*/ import_react.createElement("p", null, "You can provide a way better UX than this when your app throws errors by providing your own ", /*#__PURE__*/ import_react.createElement("code", { style: codeStyles }, "ErrorBoundary"), " or", " ", /*#__PURE__*/ import_react.createElement("code", { style: codeStyles }, "errorElement"), " prop on your route."));
	return /*#__PURE__*/ import_react.createElement(import_react.Fragment, null, /*#__PURE__*/ import_react.createElement("h2", null, "Unexpected Application Error!"), /*#__PURE__*/ import_react.createElement("h3", { style: { fontStyle: "italic" } }, message), stack ? /*#__PURE__*/ import_react.createElement("pre", { style: preStyles }, stack) : null, devInfo);
}
var defaultErrorElement = /*#__PURE__*/ import_react.createElement(DefaultErrorComponent, null);
var RenderErrorBoundary = class extends import_react.Component {
	constructor(props) {
		super(props);
		this.state = {
			location: props.location,
			revalidation: props.revalidation,
			error: props.error
		};
	}
	static getDerivedStateFromError(error) {
		return { error };
	}
	static getDerivedStateFromProps(props, state) {
		if (state.location !== props.location || state.revalidation !== "idle" && props.revalidation === "idle") return {
			error: props.error,
			location: props.location,
			revalidation: props.revalidation
		};
		return {
			error: props.error !== void 0 ? props.error : state.error,
			location: state.location,
			revalidation: props.revalidation || state.revalidation
		};
	}
	componentDidCatch(error, errorInfo) {
		console.error("React Router caught the following error during render", error, errorInfo);
	}
	render() {
		return this.state.error !== void 0 ? /*#__PURE__*/ import_react.createElement(RouteContext.Provider, { value: this.props.routeContext }, /*#__PURE__*/ import_react.createElement(RouteErrorContext.Provider, {
			value: this.state.error,
			children: this.props.component
		})) : this.props.children;
	}
};
function RenderedRoute(_ref) {
	let { routeContext, match, children } = _ref;
	let dataRouterContext = import_react.useContext(DataRouterContext);
	if (dataRouterContext && dataRouterContext.static && dataRouterContext.staticContext && (match.route.errorElement || match.route.ErrorBoundary)) dataRouterContext.staticContext._deepestRenderedBoundaryId = match.route.id;
	return /*#__PURE__*/ import_react.createElement(RouteContext.Provider, { value: routeContext }, children);
}
function _renderMatches(matches, parentMatches, dataRouterState, future) {
	var _dataRouterState;
	if (parentMatches === void 0) parentMatches = [];
	if (dataRouterState === void 0) dataRouterState = null;
	if (future === void 0) future = null;
	if (matches == null) {
		var _future;
		if (!dataRouterState) return null;
		if (dataRouterState.errors) matches = dataRouterState.matches;
		else if ((_future = future) != null && _future.v7_partialHydration && parentMatches.length === 0 && !dataRouterState.initialized && dataRouterState.matches.length > 0) matches = dataRouterState.matches;
		else return null;
	}
	let renderedMatches = matches;
	let errors = (_dataRouterState = dataRouterState) == null ? void 0 : _dataRouterState.errors;
	if (errors != null) {
		let errorIndex = renderedMatches.findIndex((m) => m.route.id && (errors == null ? void 0 : errors[m.route.id]) !== void 0);
		!(errorIndex >= 0) && invariant(false, "Could not find a matching route for errors on route IDs: " + Object.keys(errors).join(","));
		renderedMatches = renderedMatches.slice(0, Math.min(renderedMatches.length, errorIndex + 1));
	}
	let renderFallback = false;
	let fallbackIndex = -1;
	if (dataRouterState && future && future.v7_partialHydration) for (let i = 0; i < renderedMatches.length; i++) {
		let match = renderedMatches[i];
		if (match.route.HydrateFallback || match.route.hydrateFallbackElement) fallbackIndex = i;
		if (match.route.id) {
			let { loaderData, errors } = dataRouterState;
			let needsToRunLoader = match.route.loader && loaderData[match.route.id] === void 0 && (!errors || errors[match.route.id] === void 0);
			if (match.route.lazy || needsToRunLoader) {
				renderFallback = true;
				if (fallbackIndex >= 0) renderedMatches = renderedMatches.slice(0, fallbackIndex + 1);
				else renderedMatches = [renderedMatches[0]];
				break;
			}
		}
	}
	return renderedMatches.reduceRight((outlet, match, index) => {
		let error;
		let shouldRenderHydrateFallback = false;
		let errorElement = null;
		let hydrateFallbackElement = null;
		if (dataRouterState) {
			error = errors && match.route.id ? errors[match.route.id] : void 0;
			errorElement = match.route.errorElement || defaultErrorElement;
			if (renderFallback) {
				if (fallbackIndex < 0 && index === 0) {
					warningOnce("route-fallback", false, "No `HydrateFallback` element provided to render during initial hydration");
					shouldRenderHydrateFallback = true;
					hydrateFallbackElement = null;
				} else if (fallbackIndex === index) {
					shouldRenderHydrateFallback = true;
					hydrateFallbackElement = match.route.hydrateFallbackElement || null;
				}
			}
		}
		let matches = parentMatches.concat(renderedMatches.slice(0, index + 1));
		let getChildren = () => {
			let children;
			if (error) children = errorElement;
			else if (shouldRenderHydrateFallback) children = hydrateFallbackElement;
			else if (match.route.Component) children = /*#__PURE__*/ import_react.createElement(match.route.Component, null);
			else if (match.route.element) children = match.route.element;
			else children = outlet;
			return /*#__PURE__*/ import_react.createElement(RenderedRoute, {
				match,
				routeContext: {
					outlet,
					matches,
					isDataRoute: dataRouterState != null
				},
				children
			});
		};
		return dataRouterState && (match.route.ErrorBoundary || match.route.errorElement || index === 0) ? /*#__PURE__*/ import_react.createElement(RenderErrorBoundary, {
			location: dataRouterState.location,
			revalidation: dataRouterState.revalidation,
			component: errorElement,
			error,
			children: getChildren(),
			routeContext: {
				outlet: null,
				matches,
				isDataRoute: true
			}
		}) : getChildren();
	}, null);
}
var DataRouterHook$1 = /*#__PURE__*/ function(DataRouterHook) {
	DataRouterHook["UseBlocker"] = "useBlocker";
	DataRouterHook["UseRevalidator"] = "useRevalidator";
	DataRouterHook["UseNavigateStable"] = "useNavigate";
	return DataRouterHook;
}(DataRouterHook$1 || {});
var DataRouterStateHook$1 = /*#__PURE__*/ function(DataRouterStateHook) {
	DataRouterStateHook["UseBlocker"] = "useBlocker";
	DataRouterStateHook["UseLoaderData"] = "useLoaderData";
	DataRouterStateHook["UseActionData"] = "useActionData";
	DataRouterStateHook["UseRouteError"] = "useRouteError";
	DataRouterStateHook["UseNavigation"] = "useNavigation";
	DataRouterStateHook["UseRouteLoaderData"] = "useRouteLoaderData";
	DataRouterStateHook["UseMatches"] = "useMatches";
	DataRouterStateHook["UseRevalidator"] = "useRevalidator";
	DataRouterStateHook["UseNavigateStable"] = "useNavigate";
	DataRouterStateHook["UseRouteId"] = "useRouteId";
	return DataRouterStateHook;
}(DataRouterStateHook$1 || {});
function getDataRouterConsoleError$1(hookName) {
	return hookName + " must be used within a data router.  See https://reactrouter.com/v6/routers/picking-a-router.";
}
function useDataRouterContext$1(hookName) {
	let ctx = import_react.useContext(DataRouterContext);
	!ctx && invariant(false, getDataRouterConsoleError$1(hookName));
	return ctx;
}
function useDataRouterState$1(hookName) {
	let state = import_react.useContext(DataRouterStateContext);
	!state && invariant(false, getDataRouterConsoleError$1(hookName));
	return state;
}
function useRouteContext(hookName) {
	let route = import_react.useContext(RouteContext);
	!route && invariant(false, getDataRouterConsoleError$1(hookName));
	return route;
}
function useCurrentRouteId(hookName) {
	let route = useRouteContext(hookName);
	let thisRoute = route.matches[route.matches.length - 1];
	!thisRoute.route.id && invariant(false, hookName + " can only be used on routes that contain a unique \"id\"");
	return thisRoute.route.id;
}
/**
* Returns the ID for the nearest contextual route
*/
function useRouteId() {
	return useCurrentRouteId(DataRouterStateHook$1.UseRouteId);
}
/**
* Returns the current navigation, defaulting to an "idle" navigation when
* no navigation is in progress
*/
function useNavigation() {
	return useDataRouterState$1(DataRouterStateHook$1.UseNavigation).navigation;
}
/**
* Returns a revalidate function for manually triggering revalidation, as well
* as the current state of any manual revalidations
*/
function useRevalidator() {
	let dataRouterContext = useDataRouterContext$1(DataRouterHook$1.UseRevalidator);
	let state = useDataRouterState$1(DataRouterStateHook$1.UseRevalidator);
	return import_react.useMemo(() => ({
		revalidate: dataRouterContext.router.revalidate,
		state: state.revalidation
	}), [dataRouterContext.router.revalidate, state.revalidation]);
}
/**
* Returns the active route matches, useful for accessing loaderData for
* parent/child routes or the route "handle" property
*/
function useMatches() {
	let { matches, loaderData } = useDataRouterState$1(DataRouterStateHook$1.UseMatches);
	return import_react.useMemo(() => matches.map((m) => convertRouteMatchToUiMatch(m, loaderData)), [matches, loaderData]);
}
/**
* Returns the loader data for the nearest ancestor Route loader
*/
function useLoaderData() {
	let state = useDataRouterState$1(DataRouterStateHook$1.UseLoaderData);
	let routeId = useCurrentRouteId(DataRouterStateHook$1.UseLoaderData);
	if (state.errors && state.errors[routeId] != null) {
		console.error("You cannot `useLoaderData` in an errorElement (routeId: " + routeId + ")");
		return;
	}
	return state.loaderData[routeId];
}
/**
* Returns the loaderData for the given routeId
*/
function useRouteLoaderData(routeId) {
	return useDataRouterState$1(DataRouterStateHook$1.UseRouteLoaderData).loaderData[routeId];
}
/**
* Returns the action data for the nearest ancestor Route action
*/
function useActionData() {
	let state = useDataRouterState$1(DataRouterStateHook$1.UseActionData);
	let routeId = useCurrentRouteId(DataRouterStateHook$1.UseLoaderData);
	return state.actionData ? state.actionData[routeId] : void 0;
}
/**
* Returns the nearest ancestor Route error, which could be a loader/action
* error or a render error.  This is intended to be called from your
* ErrorBoundary/errorElement to display a proper error message.
*/
function useRouteError() {
	var _state$errors;
	let error = import_react.useContext(RouteErrorContext);
	let state = useDataRouterState$1(DataRouterStateHook$1.UseRouteError);
	let routeId = useCurrentRouteId(DataRouterStateHook$1.UseRouteError);
	if (error !== void 0) return error;
	return (_state$errors = state.errors) == null ? void 0 : _state$errors[routeId];
}
/**
* Returns the happy-path data from the nearest ancestor `<Await />` value
*/
function useAsyncValue() {
	let value = import_react.useContext(AwaitContext);
	return value == null ? void 0 : value._data;
}
/**
* Returns the error from the nearest ancestor `<Await />` value
*/
function useAsyncError() {
	let value = import_react.useContext(AwaitContext);
	return value == null ? void 0 : value._error;
}
var blockerId = 0;
/**
* Allow the application to block navigations within the SPA and present the
* user a confirmation dialog to confirm the navigation.  Mostly used to avoid
* using half-filled form data.  This does not handle hard-reloads or
* cross-origin navigations.
*/
function useBlocker(shouldBlock) {
	let { router, basename } = useDataRouterContext$1(DataRouterHook$1.UseBlocker);
	let state = useDataRouterState$1(DataRouterStateHook$1.UseBlocker);
	let [blockerKey, setBlockerKey] = import_react.useState("");
	let blockerFunction = import_react.useCallback((arg) => {
		if (typeof shouldBlock !== "function") return !!shouldBlock;
		if (basename === "/") return shouldBlock(arg);
		let { currentLocation, nextLocation, historyAction } = arg;
		return shouldBlock({
			currentLocation: _extends$1({}, currentLocation, { pathname: stripBasename(currentLocation.pathname, basename) || currentLocation.pathname }),
			nextLocation: _extends$1({}, nextLocation, { pathname: stripBasename(nextLocation.pathname, basename) || nextLocation.pathname }),
			historyAction
		});
	}, [basename, shouldBlock]);
	import_react.useEffect(() => {
		let key = String(++blockerId);
		setBlockerKey(key);
		return () => router.deleteBlocker(key);
	}, [router]);
	import_react.useEffect(() => {
		if (blockerKey !== "") router.getBlocker(blockerKey, blockerFunction);
	}, [
		router,
		blockerKey,
		blockerFunction
	]);
	return blockerKey && state.blockers.has(blockerKey) ? state.blockers.get(blockerKey) : IDLE_BLOCKER;
}
/**
* Stable version of useNavigate that is used when we are in the context of
* a RouterProvider.
*/
function useNavigateStable() {
	let { router } = useDataRouterContext$1(DataRouterHook$1.UseNavigateStable);
	let id = useCurrentRouteId(DataRouterStateHook$1.UseNavigateStable);
	let activeRef = import_react.useRef(false);
	useIsomorphicLayoutEffect(() => {
		activeRef.current = true;
	});
	return import_react.useCallback(function(to, options) {
		if (options === void 0) options = {};
		warning(activeRef.current, navigateEffectWarning);
		if (!activeRef.current) return;
		if (typeof to === "number") router.navigate(to);
		else router.navigate(to, _extends$1({ fromRouteId: id }, options));
	}, [router, id]);
}
var alreadyWarned$1 = {};
function warningOnce(key, cond, message) {
	if (!cond && !alreadyWarned$1[key]) {
		alreadyWarned$1[key] = true;
		warning(false, message);
	}
}
var alreadyWarned = {};
function warnOnce(key, message) {
	if (!alreadyWarned[message]) {
		alreadyWarned[message] = true;
		console.warn(message);
	}
}
var logDeprecation = (flag, msg, link) => warnOnce(flag, "⚠️ React Router Future Flag Warning: " + msg + ". " + ("You can use the `" + flag + "` future flag to opt-in early. ") + ("For more information, see " + link + "."));
function logV6DeprecationWarnings(renderFuture, routerFuture) {
	if ((renderFuture == null ? void 0 : renderFuture.v7_startTransition) === void 0) logDeprecation("v7_startTransition", "React Router will begin wrapping state updates in `React.startTransition` in v7", "https://reactrouter.com/v6/upgrading/future#v7_starttransition");
	if ((renderFuture == null ? void 0 : renderFuture.v7_relativeSplatPath) === void 0 && (!routerFuture || routerFuture.v7_relativeSplatPath === void 0)) logDeprecation("v7_relativeSplatPath", "Relative route resolution within Splat routes is changing in v7", "https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath");
	if (routerFuture) {
		if (routerFuture.v7_fetcherPersist === void 0) logDeprecation("v7_fetcherPersist", "The persistence behavior of fetchers is changing in v7", "https://reactrouter.com/v6/upgrading/future#v7_fetcherpersist");
		if (routerFuture.v7_normalizeFormMethod === void 0) logDeprecation("v7_normalizeFormMethod", "Casing of `formMethod` fields is being normalized to uppercase in v7", "https://reactrouter.com/v6/upgrading/future#v7_normalizeformmethod");
		if (routerFuture.v7_partialHydration === void 0) logDeprecation("v7_partialHydration", "`RouterProvider` hydration behavior is changing in v7", "https://reactrouter.com/v6/upgrading/future#v7_partialhydration");
		if (routerFuture.v7_skipActionErrorRevalidation === void 0) logDeprecation("v7_skipActionErrorRevalidation", "The revalidation behavior after 4xx/5xx `action` responses is changing in v7", "https://reactrouter.com/v6/upgrading/future#v7_skipactionerrorrevalidation");
	}
}
var startTransitionImpl$1 = import_react.startTransition;
/**
* A `<Router>` that stores all entries in memory.
*
* @see https://reactrouter.com/v6/router-components/memory-router
*/
function MemoryRouter(_ref3) {
	let { basename, children, initialEntries, initialIndex, future } = _ref3;
	let historyRef = import_react.useRef();
	if (historyRef.current == null) historyRef.current = createMemoryHistory({
		initialEntries,
		initialIndex,
		v5Compat: true
	});
	let history = historyRef.current;
	let [state, setStateImpl] = import_react.useState({
		action: history.action,
		location: history.location
	});
	let { v7_startTransition } = future || {};
	let setState = import_react.useCallback((newState) => {
		v7_startTransition && startTransitionImpl$1 ? startTransitionImpl$1(() => setStateImpl(newState)) : setStateImpl(newState);
	}, [setStateImpl, v7_startTransition]);
	import_react.useLayoutEffect(() => history.listen(setState), [history, setState]);
	import_react.useEffect(() => logV6DeprecationWarnings(future), [future]);
	return /*#__PURE__*/ import_react.createElement(Router, {
		basename,
		children,
		location: state.location,
		navigationType: state.action,
		navigator: history,
		future
	});
}
/**
* Changes the current location.
*
* Note: This API is mostly useful in React.Component subclasses that are not
* able to use hooks. In functional components, we recommend you use the
* `useNavigate` hook instead.
*
* @see https://reactrouter.com/v6/components/navigate
*/
function Navigate(_ref4) {
	let { to, replace, state, relative } = _ref4;
	!useInRouterContext() && invariant(false, "<Navigate> may be used only in the context of a <Router> component.");
	let { future, static: isStatic } = import_react.useContext(NavigationContext);
	warning(!isStatic, "<Navigate> must not be used on the initial render in a <StaticRouter>. This is a no-op, but you should modify your code so the <Navigate> is only ever rendered in response to some user interaction or state change.");
	let { matches } = import_react.useContext(RouteContext);
	let { pathname: locationPathname } = useLocation();
	let navigate = useNavigate();
	let path = resolveTo(to, getResolveToMatches(matches, future.v7_relativeSplatPath), locationPathname, relative === "path");
	let jsonPath = JSON.stringify(path);
	import_react.useEffect(() => navigate(JSON.parse(jsonPath), {
		replace,
		state,
		relative
	}), [
		navigate,
		jsonPath,
		relative,
		replace,
		state
	]);
	return null;
}
/**
* Renders the child route's element, if there is one.
*
* @see https://reactrouter.com/v6/components/outlet
*/
function Outlet(props) {
	return useOutlet(props.context);
}
/**
* Declares an element that should be rendered at a certain URL path.
*
* @see https://reactrouter.com/v6/components/route
*/
function Route(_props) {
	invariant(false, "A <Route> is only ever to be used as the child of <Routes> element, never rendered directly. Please wrap your <Route> in a <Routes>.");
}
/**
* Provides location context for the rest of the app.
*
* Note: You usually won't render a `<Router>` directly. Instead, you'll render a
* router that is more specific to your environment such as a `<BrowserRouter>`
* in web browsers or a `<StaticRouter>` for server rendering.
*
* @see https://reactrouter.com/v6/router-components/router
*/
function Router(_ref5) {
	let { basename: basenameProp = "/", children = null, location: locationProp, navigationType = Action.Pop, navigator, static: staticProp = false, future } = _ref5;
	useInRouterContext() && invariant(false, "You cannot render a <Router> inside another <Router>. You should never have more than one in your app.");
	let basename = basenameProp.replace(/^\/*/, "/");
	let navigationContext = import_react.useMemo(() => ({
		basename,
		navigator,
		static: staticProp,
		future: _extends$1({ v7_relativeSplatPath: false }, future)
	}), [
		basename,
		future,
		navigator,
		staticProp
	]);
	if (typeof locationProp === "string") locationProp = parsePath(locationProp);
	let { pathname = "/", search = "", hash = "", state = null, key = "default" } = locationProp;
	let locationContext = import_react.useMemo(() => {
		let trailingPathname = stripBasename(pathname, basename);
		if (trailingPathname == null) return null;
		return {
			location: {
				pathname: trailingPathname,
				search,
				hash,
				state,
				key
			},
			navigationType
		};
	}, [
		basename,
		pathname,
		search,
		hash,
		state,
		key,
		navigationType
	]);
	warning(locationContext != null, "<Router basename=\"" + basename + "\"> is not able to match the URL " + ("\"" + pathname + search + hash + "\" because it does not start with the ") + "basename, so the <Router> won't render anything.");
	if (locationContext == null) return null;
	return /*#__PURE__*/ import_react.createElement(NavigationContext.Provider, { value: navigationContext }, /*#__PURE__*/ import_react.createElement(LocationContext.Provider, {
		children,
		value: locationContext
	}));
}
/**
* A container for a nested tree of `<Route>` elements that renders the branch
* that best matches the current location.
*
* @see https://reactrouter.com/v6/components/routes
*/
function Routes(_ref6) {
	let { children, location } = _ref6;
	return useRoutes(createRoutesFromChildren(children), location);
}
/**
* Component to use for rendering lazily loaded data from returning defer()
* in a loader function
*/
function Await(_ref7) {
	let { children, errorElement, resolve } = _ref7;
	return /*#__PURE__*/ import_react.createElement(AwaitErrorBoundary, {
		resolve,
		errorElement
	}, /*#__PURE__*/ import_react.createElement(ResolveAwait, null, children));
}
var AwaitRenderStatus = /*#__PURE__*/ function(AwaitRenderStatus) {
	AwaitRenderStatus[AwaitRenderStatus["pending"] = 0] = "pending";
	AwaitRenderStatus[AwaitRenderStatus["success"] = 1] = "success";
	AwaitRenderStatus[AwaitRenderStatus["error"] = 2] = "error";
	return AwaitRenderStatus;
}(AwaitRenderStatus || {});
var neverSettledPromise = new Promise(() => {});
var AwaitErrorBoundary = class extends import_react.Component {
	constructor(props) {
		super(props);
		this.state = { error: null };
	}
	static getDerivedStateFromError(error) {
		return { error };
	}
	componentDidCatch(error, errorInfo) {
		console.error("<Await> caught the following error during render", error, errorInfo);
	}
	render() {
		let { children, errorElement, resolve } = this.props;
		let promise = null;
		let status = AwaitRenderStatus.pending;
		if (!(resolve instanceof Promise)) {
			status = AwaitRenderStatus.success;
			promise = Promise.resolve();
			Object.defineProperty(promise, "_tracked", { get: () => true });
			Object.defineProperty(promise, "_data", { get: () => resolve });
		} else if (this.state.error) {
			status = AwaitRenderStatus.error;
			let renderError = this.state.error;
			promise = Promise.reject().catch(() => {});
			Object.defineProperty(promise, "_tracked", { get: () => true });
			Object.defineProperty(promise, "_error", { get: () => renderError });
		} else if (resolve._tracked) {
			promise = resolve;
			status = "_error" in promise ? AwaitRenderStatus.error : "_data" in promise ? AwaitRenderStatus.success : AwaitRenderStatus.pending;
		} else {
			status = AwaitRenderStatus.pending;
			Object.defineProperty(resolve, "_tracked", { get: () => true });
			promise = resolve.then((data) => Object.defineProperty(resolve, "_data", { get: () => data }), (error) => Object.defineProperty(resolve, "_error", { get: () => error }));
		}
		if (status === AwaitRenderStatus.error && promise._error instanceof AbortedDeferredError) throw neverSettledPromise;
		if (status === AwaitRenderStatus.error && !errorElement) throw promise._error;
		if (status === AwaitRenderStatus.error) return /*#__PURE__*/ import_react.createElement(AwaitContext.Provider, {
			value: promise,
			children: errorElement
		});
		if (status === AwaitRenderStatus.success) return /*#__PURE__*/ import_react.createElement(AwaitContext.Provider, {
			value: promise,
			children
		});
		throw promise;
	}
};
/**
* @private
* Indirection to leverage useAsyncValue for a render-prop API on `<Await>`
*/
function ResolveAwait(_ref8) {
	let { children } = _ref8;
	let data = useAsyncValue();
	let toRender = typeof children === "function" ? children(data) : children;
	return /*#__PURE__*/ import_react.createElement(import_react.Fragment, null, toRender);
}
/**
* Creates a route config from a React "children" object, which is usually
* either a `<Route>` element or an array of them. Used internally by
* `<Routes>` to create a route config from its children.
*
* @see https://reactrouter.com/v6/utils/create-routes-from-children
*/
function createRoutesFromChildren(children, parentPath) {
	if (parentPath === void 0) parentPath = [];
	let routes = [];
	import_react.Children.forEach(children, (element, index) => {
		if (!/*#__PURE__*/ import_react.isValidElement(element)) return;
		let treePath = [...parentPath, index];
		if (element.type === import_react.Fragment) {
			routes.push.apply(routes, createRoutesFromChildren(element.props.children, treePath));
			return;
		}
		!(element.type === Route) && invariant(false, "[" + (typeof element.type === "string" ? element.type : element.type.name) + "] is not a <Route> component. All component children of <Routes> must be a <Route> or <React.Fragment>");
		!(!element.props.index || !element.props.children) && invariant(false, "An index route cannot have child routes.");
		let route = {
			id: element.props.id || treePath.join("-"),
			caseSensitive: element.props.caseSensitive,
			element: element.props.element,
			Component: element.props.Component,
			index: element.props.index,
			path: element.props.path,
			loader: element.props.loader,
			action: element.props.action,
			errorElement: element.props.errorElement,
			ErrorBoundary: element.props.ErrorBoundary,
			hasErrorBoundary: element.props.ErrorBoundary != null || element.props.errorElement != null,
			shouldRevalidate: element.props.shouldRevalidate,
			handle: element.props.handle,
			lazy: element.props.lazy
		};
		if (element.props.children) route.children = createRoutesFromChildren(element.props.children, treePath);
		routes.push(route);
	});
	return routes;
}
/**
* Renders the result of `matchRoutes()` into a React element.
*/
function renderMatches(matches) {
	return _renderMatches(matches);
}
function mapRouteProperties(route) {
	let updates = { hasErrorBoundary: route.ErrorBoundary != null || route.errorElement != null };
	if (route.Component) {
		if (route.element) warning(false, "You should not include both `Component` and `element` on your route - `Component` will be used.");
		Object.assign(updates, {
			element: /*#__PURE__*/ import_react.createElement(route.Component),
			Component: void 0
		});
	}
	if (route.HydrateFallback) {
		if (route.hydrateFallbackElement) warning(false, "You should not include both `HydrateFallback` and `hydrateFallbackElement` on your route - `HydrateFallback` will be used.");
		Object.assign(updates, {
			hydrateFallbackElement: /*#__PURE__*/ import_react.createElement(route.HydrateFallback),
			HydrateFallback: void 0
		});
	}
	if (route.ErrorBoundary) {
		if (route.errorElement) warning(false, "You should not include both `ErrorBoundary` and `errorElement` on your route - `ErrorBoundary` will be used.");
		Object.assign(updates, {
			errorElement: /*#__PURE__*/ import_react.createElement(route.ErrorBoundary),
			ErrorBoundary: void 0
		});
	}
	return updates;
}
function createMemoryRouter(routes, opts) {
	return createRouter({
		basename: opts == null ? void 0 : opts.basename,
		future: _extends$1({}, opts == null ? void 0 : opts.future, { v7_prependBasename: true }),
		history: createMemoryHistory({
			initialEntries: opts == null ? void 0 : opts.initialEntries,
			initialIndex: opts == null ? void 0 : opts.initialIndex
		}),
		hydrationData: opts == null ? void 0 : opts.hydrationData,
		routes,
		mapRouteProperties,
		dataStrategy: opts == null ? void 0 : opts.dataStrategy,
		patchRoutesOnNavigation: opts == null ? void 0 : opts.patchRoutesOnNavigation
	}).initialize();
}
//#endregion
//#region node_modules/react-router-dom/dist/index.js
/**
* React Router DOM v6.30.4
*
* Copyright (c) Remix Software Inc.
*
* This source code is licensed under the MIT license found in the
* LICENSE.md file in the root directory of this source tree.
*
* @license MIT
*/
function _extends() {
	return _extends = Object.assign ? Object.assign.bind() : function(n) {
		for (var e = 1; e < arguments.length; e++) {
			var t = arguments[e];
			for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
		}
		return n;
	}, _extends.apply(null, arguments);
}
function _objectWithoutPropertiesLoose(r, e) {
	if (null == r) return {};
	var t = {};
	for (var n in r) if ({}.hasOwnProperty.call(r, n)) {
		if (-1 !== e.indexOf(n)) continue;
		t[n] = r[n];
	}
	return t;
}
var defaultMethod = "get";
var defaultEncType = "application/x-www-form-urlencoded";
function isHtmlElement(object) {
	return object != null && typeof object.tagName === "string";
}
function isButtonElement(object) {
	return isHtmlElement(object) && object.tagName.toLowerCase() === "button";
}
function isFormElement(object) {
	return isHtmlElement(object) && object.tagName.toLowerCase() === "form";
}
function isInputElement(object) {
	return isHtmlElement(object) && object.tagName.toLowerCase() === "input";
}
function isModifiedEvent(event) {
	return !!(event.metaKey || event.altKey || event.ctrlKey || event.shiftKey);
}
function shouldProcessLinkClick(event, target) {
	return event.button === 0 && (!target || target === "_self") && !isModifiedEvent(event);
}
/**
* Creates a URLSearchParams object using the given initializer.
*
* This is identical to `new URLSearchParams(init)` except it also
* supports arrays as values in the object form of the initializer
* instead of just strings. This is convenient when you need multiple
* values for a given key, but don't want to use an array initializer.
*
* For example, instead of:
*
*   let searchParams = new URLSearchParams([
*     ['sort', 'name'],
*     ['sort', 'price']
*   ]);
*
* you can do:
*
*   let searchParams = createSearchParams({
*     sort: ['name', 'price']
*   });
*/
function createSearchParams(init) {
	if (init === void 0) init = "";
	return new URLSearchParams(typeof init === "string" || Array.isArray(init) || init instanceof URLSearchParams ? init : Object.keys(init).reduce((memo, key) => {
		let value = init[key];
		return memo.concat(Array.isArray(value) ? value.map((v) => [key, v]) : [[key, value]]);
	}, []));
}
function getSearchParamsForLocation(locationSearch, defaultSearchParams) {
	let searchParams = createSearchParams(locationSearch);
	if (defaultSearchParams) defaultSearchParams.forEach((_, key) => {
		if (!searchParams.has(key)) defaultSearchParams.getAll(key).forEach((value) => {
			searchParams.append(key, value);
		});
	});
	return searchParams;
}
var _formDataSupportsSubmitter = null;
function isFormDataSubmitterSupported() {
	if (_formDataSupportsSubmitter === null) try {
		new FormData(document.createElement("form"), 0);
		_formDataSupportsSubmitter = false;
	} catch (e) {
		_formDataSupportsSubmitter = true;
	}
	return _formDataSupportsSubmitter;
}
var supportedFormEncTypes = new Set([
	"application/x-www-form-urlencoded",
	"multipart/form-data",
	"text/plain"
]);
function getFormEncType(encType) {
	if (encType != null && !supportedFormEncTypes.has(encType)) {
		warning(false, "\"" + encType + "\" is not a valid `encType` for `<Form>`/`<fetcher.Form>` and will default to \"application/x-www-form-urlencoded\"");
		return null;
	}
	return encType;
}
function getFormSubmissionInfo(target, basename) {
	let method;
	let action;
	let encType;
	let formData;
	let body;
	if (isFormElement(target)) {
		let attr = target.getAttribute("action");
		action = attr ? stripBasename(attr, basename) : null;
		method = target.getAttribute("method") || defaultMethod;
		encType = getFormEncType(target.getAttribute("enctype")) || defaultEncType;
		formData = new FormData(target);
	} else if (isButtonElement(target) || isInputElement(target) && (target.type === "submit" || target.type === "image")) {
		let form = target.form;
		if (form == null) throw new Error("Cannot submit a <button> or <input type=\"submit\"> without a <form>");
		let attr = target.getAttribute("formaction") || form.getAttribute("action");
		action = attr ? stripBasename(attr, basename) : null;
		method = target.getAttribute("formmethod") || form.getAttribute("method") || defaultMethod;
		encType = getFormEncType(target.getAttribute("formenctype")) || getFormEncType(form.getAttribute("enctype")) || defaultEncType;
		formData = new FormData(form, target);
		if (!isFormDataSubmitterSupported()) {
			let { name, type, value } = target;
			if (type === "image") {
				let prefix = name ? name + "." : "";
				formData.append(prefix + "x", "0");
				formData.append(prefix + "y", "0");
			} else if (name) formData.append(name, value);
		}
	} else if (isHtmlElement(target)) throw new Error("Cannot submit element that is not <form>, <button>, or <input type=\"submit|image\">");
	else {
		method = defaultMethod;
		action = null;
		encType = defaultEncType;
		body = target;
	}
	if (formData && encType === "text/plain") {
		body = formData;
		formData = void 0;
	}
	return {
		action,
		method: method.toLowerCase(),
		encType,
		formData,
		body
	};
}
var _excluded = [
	"onClick",
	"relative",
	"reloadDocument",
	"replace",
	"state",
	"target",
	"to",
	"preventScrollReset",
	"viewTransition"
], _excluded2 = [
	"aria-current",
	"caseSensitive",
	"className",
	"end",
	"style",
	"to",
	"viewTransition",
	"children"
], _excluded3 = [
	"fetcherKey",
	"navigate",
	"reloadDocument",
	"replace",
	"state",
	"method",
	"action",
	"onSubmit",
	"relative",
	"preventScrollReset",
	"viewTransition"
];
var REACT_ROUTER_VERSION = "6";
try {
	window.__reactRouterVersion = REACT_ROUTER_VERSION;
} catch (e) {}
function createBrowserRouter(routes, opts) {
	return createRouter({
		basename: opts == null ? void 0 : opts.basename,
		future: _extends({}, opts == null ? void 0 : opts.future, { v7_prependBasename: true }),
		history: createBrowserHistory({ window: opts == null ? void 0 : opts.window }),
		hydrationData: (opts == null ? void 0 : opts.hydrationData) || parseHydrationData(),
		routes,
		mapRouteProperties,
		dataStrategy: opts == null ? void 0 : opts.dataStrategy,
		patchRoutesOnNavigation: opts == null ? void 0 : opts.patchRoutesOnNavigation,
		window: opts == null ? void 0 : opts.window
	}).initialize();
}
function createHashRouter(routes, opts) {
	return createRouter({
		basename: opts == null ? void 0 : opts.basename,
		future: _extends({}, opts == null ? void 0 : opts.future, { v7_prependBasename: true }),
		history: createHashHistory({ window: opts == null ? void 0 : opts.window }),
		hydrationData: (opts == null ? void 0 : opts.hydrationData) || parseHydrationData(),
		routes,
		mapRouteProperties,
		dataStrategy: opts == null ? void 0 : opts.dataStrategy,
		patchRoutesOnNavigation: opts == null ? void 0 : opts.patchRoutesOnNavigation,
		window: opts == null ? void 0 : opts.window
	}).initialize();
}
function parseHydrationData() {
	var _window;
	let state = (_window = window) == null ? void 0 : _window.__staticRouterHydrationData;
	if (state && state.errors) state = _extends({}, state, { errors: deserializeErrors(state.errors) });
	return state;
}
function deserializeErrors(errors) {
	if (!errors) return null;
	let entries = Object.entries(errors);
	let serialized = {};
	for (let [key, val] of entries) if (val && val.__type === "RouteErrorResponse") serialized[key] = new ErrorResponseImpl(val.status, val.statusText, val.data, val.internal === true);
	else if (val && val.__type === "Error") {
		if (val.__subType) {
			let ErrorConstructor = window[val.__subType];
			if (typeof ErrorConstructor === "function") try {
				let error = new ErrorConstructor(val.message);
				error.stack = "";
				serialized[key] = error;
			} catch (e) {}
		}
		if (serialized[key] == null) {
			let error = new Error(val.message);
			error.stack = "";
			serialized[key] = error;
		}
	} else serialized[key] = val;
	return serialized;
}
var ViewTransitionContext = /*#__PURE__*/ import_react.createContext({ isTransitioning: false });
ViewTransitionContext.displayName = "ViewTransition";
var FetchersContext = /*#__PURE__*/ import_react.createContext(/* @__PURE__ */ new Map());
FetchersContext.displayName = "Fetchers";
var startTransitionImpl = import_react.startTransition;
var flushSyncImpl = import_react_dom.flushSync;
var useIdImpl = import_react.useId;
function startTransitionSafe(cb) {
	if (startTransitionImpl) startTransitionImpl(cb);
	else cb();
}
function flushSyncSafe(cb) {
	if (flushSyncImpl) flushSyncImpl(cb);
	else cb();
}
var Deferred = class {
	constructor() {
		this.status = "pending";
		this.promise = new Promise((resolve, reject) => {
			this.resolve = (value) => {
				if (this.status === "pending") {
					this.status = "resolved";
					resolve(value);
				}
			};
			this.reject = (reason) => {
				if (this.status === "pending") {
					this.status = "rejected";
					reject(reason);
				}
			};
		});
	}
};
/**
* Given a Remix Router instance, render the appropriate UI
*/
function RouterProvider(_ref) {
	let { fallbackElement, router, future } = _ref;
	let [state, setStateImpl] = import_react.useState(router.state);
	let [pendingState, setPendingState] = import_react.useState();
	let [vtContext, setVtContext] = import_react.useState({ isTransitioning: false });
	let [renderDfd, setRenderDfd] = import_react.useState();
	let [transition, setTransition] = import_react.useState();
	let [interruption, setInterruption] = import_react.useState();
	let fetcherData = import_react.useRef(/* @__PURE__ */ new Map());
	let { v7_startTransition } = future || {};
	let optInStartTransition = import_react.useCallback((cb) => {
		if (v7_startTransition) startTransitionSafe(cb);
		else cb();
	}, [v7_startTransition]);
	let setState = import_react.useCallback((newState, _ref2) => {
		let { deletedFetchers, flushSync, viewTransitionOpts } = _ref2;
		newState.fetchers.forEach((fetcher, key) => {
			if (fetcher.data !== void 0) fetcherData.current.set(key, fetcher.data);
		});
		deletedFetchers.forEach((key) => fetcherData.current.delete(key));
		let isViewTransitionUnavailable = router.window == null || router.window.document == null || typeof router.window.document.startViewTransition !== "function";
		if (!viewTransitionOpts || isViewTransitionUnavailable) {
			if (flushSync) flushSyncSafe(() => setStateImpl(newState));
			else optInStartTransition(() => setStateImpl(newState));
			return;
		}
		if (flushSync) {
			flushSyncSafe(() => {
				if (transition) {
					renderDfd && renderDfd.resolve();
					transition.skipTransition();
				}
				setVtContext({
					isTransitioning: true,
					flushSync: true,
					currentLocation: viewTransitionOpts.currentLocation,
					nextLocation: viewTransitionOpts.nextLocation
				});
			});
			let t = router.window.document.startViewTransition(() => {
				flushSyncSafe(() => setStateImpl(newState));
			});
			t.finished.finally(() => {
				flushSyncSafe(() => {
					setRenderDfd(void 0);
					setTransition(void 0);
					setPendingState(void 0);
					setVtContext({ isTransitioning: false });
				});
			});
			flushSyncSafe(() => setTransition(t));
			return;
		}
		if (transition) {
			renderDfd && renderDfd.resolve();
			transition.skipTransition();
			setInterruption({
				state: newState,
				currentLocation: viewTransitionOpts.currentLocation,
				nextLocation: viewTransitionOpts.nextLocation
			});
		} else {
			setPendingState(newState);
			setVtContext({
				isTransitioning: true,
				flushSync: false,
				currentLocation: viewTransitionOpts.currentLocation,
				nextLocation: viewTransitionOpts.nextLocation
			});
		}
	}, [
		router.window,
		transition,
		renderDfd,
		fetcherData,
		optInStartTransition
	]);
	import_react.useLayoutEffect(() => router.subscribe(setState), [router, setState]);
	import_react.useEffect(() => {
		if (vtContext.isTransitioning && !vtContext.flushSync) setRenderDfd(new Deferred());
	}, [vtContext]);
	import_react.useEffect(() => {
		if (renderDfd && pendingState && router.window) {
			let newState = pendingState;
			let renderPromise = renderDfd.promise;
			let transition = router.window.document.startViewTransition(async () => {
				optInStartTransition(() => setStateImpl(newState));
				await renderPromise;
			});
			transition.finished.finally(() => {
				setRenderDfd(void 0);
				setTransition(void 0);
				setPendingState(void 0);
				setVtContext({ isTransitioning: false });
			});
			setTransition(transition);
		}
	}, [
		optInStartTransition,
		pendingState,
		renderDfd,
		router.window
	]);
	import_react.useEffect(() => {
		if (renderDfd && pendingState && state.location.key === pendingState.location.key) renderDfd.resolve();
	}, [
		renderDfd,
		transition,
		state.location,
		pendingState
	]);
	import_react.useEffect(() => {
		if (!vtContext.isTransitioning && interruption) {
			setPendingState(interruption.state);
			setVtContext({
				isTransitioning: true,
				flushSync: false,
				currentLocation: interruption.currentLocation,
				nextLocation: interruption.nextLocation
			});
			setInterruption(void 0);
		}
	}, [vtContext.isTransitioning, interruption]);
	import_react.useEffect(() => {
		warning(fallbackElement == null || !router.future.v7_partialHydration, "`<RouterProvider fallbackElement>` is deprecated when using `v7_partialHydration`, use a `HydrateFallback` component instead");
	}, []);
	let navigator = import_react.useMemo(() => {
		return {
			createHref: router.createHref,
			encodeLocation: router.encodeLocation,
			go: (n) => router.navigate(n),
			push: (to, state, opts) => router.navigate(to, {
				state,
				preventScrollReset: opts == null ? void 0 : opts.preventScrollReset
			}),
			replace: (to, state, opts) => router.navigate(to, {
				replace: true,
				state,
				preventScrollReset: opts == null ? void 0 : opts.preventScrollReset
			})
		};
	}, [router]);
	let basename = router.basename || "/";
	let dataRouterContext = import_react.useMemo(() => ({
		router,
		navigator,
		static: false,
		basename
	}), [
		router,
		navigator,
		basename
	]);
	let routerFuture = import_react.useMemo(() => ({ v7_relativeSplatPath: router.future.v7_relativeSplatPath }), [router.future.v7_relativeSplatPath]);
	import_react.useEffect(() => logV6DeprecationWarnings(future, router.future), [future, router.future]);
	return /*#__PURE__*/ import_react.createElement(import_react.Fragment, null, /*#__PURE__*/ import_react.createElement(DataRouterContext.Provider, { value: dataRouterContext }, /*#__PURE__*/ import_react.createElement(DataRouterStateContext.Provider, { value: state }, /*#__PURE__*/ import_react.createElement(FetchersContext.Provider, { value: fetcherData.current }, /*#__PURE__*/ import_react.createElement(ViewTransitionContext.Provider, { value: vtContext }, /*#__PURE__*/ import_react.createElement(Router, {
		basename,
		location: state.location,
		navigationType: state.historyAction,
		navigator,
		future: routerFuture
	}, state.initialized || router.future.v7_partialHydration ? /*#__PURE__*/ import_react.createElement(MemoizedDataRoutes, {
		routes: router.routes,
		future: router.future,
		state
	}) : fallbackElement))))), null);
}
var MemoizedDataRoutes = /*#__PURE__*/ import_react.memo(DataRoutes);
function DataRoutes(_ref3) {
	let { routes, future, state } = _ref3;
	return useRoutesImpl(routes, void 0, state, future);
}
/**
* A `<Router>` for use in web browsers. Provides the cleanest URLs.
*/
function BrowserRouter(_ref4) {
	let { basename, children, future, window } = _ref4;
	let historyRef = import_react.useRef();
	if (historyRef.current == null) historyRef.current = createBrowserHistory({
		window,
		v5Compat: true
	});
	let history = historyRef.current;
	let [state, setStateImpl] = import_react.useState({
		action: history.action,
		location: history.location
	});
	let { v7_startTransition } = future || {};
	let setState = import_react.useCallback((newState) => {
		v7_startTransition && startTransitionImpl ? startTransitionImpl(() => setStateImpl(newState)) : setStateImpl(newState);
	}, [setStateImpl, v7_startTransition]);
	import_react.useLayoutEffect(() => history.listen(setState), [history, setState]);
	import_react.useEffect(() => logV6DeprecationWarnings(future), [future]);
	return /*#__PURE__*/ import_react.createElement(Router, {
		basename,
		children,
		location: state.location,
		navigationType: state.action,
		navigator: history,
		future
	});
}
/**
* A `<Router>` for use in web browsers. Stores the location in the hash
* portion of the URL so it is not sent to the server.
*/
function HashRouter(_ref5) {
	let { basename, children, future, window } = _ref5;
	let historyRef = import_react.useRef();
	if (historyRef.current == null) historyRef.current = createHashHistory({
		window,
		v5Compat: true
	});
	let history = historyRef.current;
	let [state, setStateImpl] = import_react.useState({
		action: history.action,
		location: history.location
	});
	let { v7_startTransition } = future || {};
	let setState = import_react.useCallback((newState) => {
		v7_startTransition && startTransitionImpl ? startTransitionImpl(() => setStateImpl(newState)) : setStateImpl(newState);
	}, [setStateImpl, v7_startTransition]);
	import_react.useLayoutEffect(() => history.listen(setState), [history, setState]);
	import_react.useEffect(() => logV6DeprecationWarnings(future), [future]);
	return /*#__PURE__*/ import_react.createElement(Router, {
		basename,
		children,
		location: state.location,
		navigationType: state.action,
		navigator: history,
		future
	});
}
/**
* A `<Router>` that accepts a pre-instantiated history object. It's important
* to note that using your own history object is highly discouraged and may add
* two versions of the history library to your bundles unless you use the same
* version of the history library that React Router uses internally.
*/
function HistoryRouter(_ref6) {
	let { basename, children, future, history } = _ref6;
	let [state, setStateImpl] = import_react.useState({
		action: history.action,
		location: history.location
	});
	let { v7_startTransition } = future || {};
	let setState = import_react.useCallback((newState) => {
		v7_startTransition && startTransitionImpl ? startTransitionImpl(() => setStateImpl(newState)) : setStateImpl(newState);
	}, [setStateImpl, v7_startTransition]);
	import_react.useLayoutEffect(() => history.listen(setState), [history, setState]);
	import_react.useEffect(() => logV6DeprecationWarnings(future), [future]);
	return /*#__PURE__*/ import_react.createElement(Router, {
		basename,
		children,
		location: state.location,
		navigationType: state.action,
		navigator: history,
		future
	});
}
HistoryRouter.displayName = "unstable_HistoryRouter";
var isBrowser = typeof window !== "undefined" && typeof window.document !== "undefined" && typeof window.document.createElement !== "undefined";
var ABSOLUTE_URL_REGEX = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;
/**
* The public API for rendering a history-aware `<a>`.
*/
var Link = /*#__PURE__*/ import_react.forwardRef(function LinkWithRef(_ref7, ref) {
	let { onClick, relative, reloadDocument, replace, state, target, to, preventScrollReset, viewTransition } = _ref7, rest = _objectWithoutPropertiesLoose(_ref7, _excluded);
	let { basename } = import_react.useContext(NavigationContext);
	let absoluteHref;
	let isExternal = false;
	if (typeof to === "string" && ABSOLUTE_URL_REGEX.test(to)) {
		absoluteHref = to;
		if (isBrowser) try {
			let currentUrl = new URL(window.location.href);
			let targetUrl = to.startsWith("//") ? new URL(currentUrl.protocol + to) : new URL(to);
			let path = stripBasename(targetUrl.pathname, basename);
			if (targetUrl.origin === currentUrl.origin && path != null) to = path + targetUrl.search + targetUrl.hash;
			else isExternal = true;
		} catch (e) {
			warning(false, "<Link to=\"" + to + "\"> contains an invalid URL which will probably break when clicked - please update to a valid URL path.");
		}
	}
	let href = useHref(to, { relative });
	let internalOnClick = useLinkClickHandler(to, {
		replace,
		state,
		target,
		preventScrollReset,
		relative,
		viewTransition
	});
	function handleClick(event) {
		if (onClick) onClick(event);
		if (!event.defaultPrevented) internalOnClick(event);
	}
	return /*#__PURE__*/ import_react.createElement("a", _extends({}, rest, {
		href: absoluteHref || href,
		onClick: isExternal || reloadDocument ? onClick : handleClick,
		ref,
		target
	}));
});
Link.displayName = "Link";
/**
* A `<Link>` wrapper that knows if it's "active" or not.
*/
var NavLink = /*#__PURE__*/ import_react.forwardRef(function NavLinkWithRef(_ref8, ref) {
	let { "aria-current": ariaCurrentProp = "page", caseSensitive = false, className: classNameProp = "", end = false, style: styleProp, to, viewTransition, children } = _ref8, rest = _objectWithoutPropertiesLoose(_ref8, _excluded2);
	let path = useResolvedPath(to, { relative: rest.relative });
	let location = useLocation();
	let routerState = import_react.useContext(DataRouterStateContext);
	let { navigator, basename } = import_react.useContext(NavigationContext);
	let isTransitioning = routerState != null && useViewTransitionState(path) && viewTransition === true;
	let toPathname = navigator.encodeLocation ? navigator.encodeLocation(path).pathname : path.pathname;
	let locationPathname = location.pathname;
	let nextLocationPathname = routerState && routerState.navigation && routerState.navigation.location ? routerState.navigation.location.pathname : null;
	if (!caseSensitive) {
		locationPathname = locationPathname.toLowerCase();
		nextLocationPathname = nextLocationPathname ? nextLocationPathname.toLowerCase() : null;
		toPathname = toPathname.toLowerCase();
	}
	if (nextLocationPathname && basename) nextLocationPathname = stripBasename(nextLocationPathname, basename) || nextLocationPathname;
	const endSlashPosition = toPathname !== "/" && toPathname.endsWith("/") ? toPathname.length - 1 : toPathname.length;
	let isActive = locationPathname === toPathname || !end && locationPathname.startsWith(toPathname) && locationPathname.charAt(endSlashPosition) === "/";
	let isPending = nextLocationPathname != null && (nextLocationPathname === toPathname || !end && nextLocationPathname.startsWith(toPathname) && nextLocationPathname.charAt(toPathname.length) === "/");
	let renderProps = {
		isActive,
		isPending,
		isTransitioning
	};
	let ariaCurrent = isActive ? ariaCurrentProp : void 0;
	let className;
	if (typeof classNameProp === "function") className = classNameProp(renderProps);
	else className = [
		classNameProp,
		isActive ? "active" : null,
		isPending ? "pending" : null,
		isTransitioning ? "transitioning" : null
	].filter(Boolean).join(" ");
	let style = typeof styleProp === "function" ? styleProp(renderProps) : styleProp;
	return /*#__PURE__*/ import_react.createElement(Link, _extends({}, rest, {
		"aria-current": ariaCurrent,
		className,
		ref,
		style,
		to,
		viewTransition
	}), typeof children === "function" ? children(renderProps) : children);
});
NavLink.displayName = "NavLink";
/**
* A `@remix-run/router`-aware `<form>`. It behaves like a normal form except
* that the interaction with the server is with `fetch` instead of new document
* requests, allowing components to add nicer UX to the page as the form is
* submitted and returns with data.
*/
var Form = /*#__PURE__*/ import_react.forwardRef((_ref9, forwardedRef) => {
	let { fetcherKey, navigate, reloadDocument, replace, state, method = defaultMethod, action, onSubmit, relative, preventScrollReset, viewTransition } = _ref9, props = _objectWithoutPropertiesLoose(_ref9, _excluded3);
	let submit = useSubmit();
	let formAction = useFormAction(action, { relative });
	let formMethod = method.toLowerCase() === "get" ? "get" : "post";
	let submitHandler = (event) => {
		onSubmit && onSubmit(event);
		if (event.defaultPrevented) return;
		event.preventDefault();
		let submitter = event.nativeEvent.submitter;
		let submitMethod = (submitter == null ? void 0 : submitter.getAttribute("formmethod")) || method;
		submit(submitter || event.currentTarget, {
			fetcherKey,
			method: submitMethod,
			navigate,
			replace,
			state,
			relative,
			preventScrollReset,
			viewTransition
		});
	};
	return /*#__PURE__*/ import_react.createElement("form", _extends({
		ref: forwardedRef,
		method: formMethod,
		action: formAction,
		onSubmit: reloadDocument ? onSubmit : submitHandler
	}, props));
});
Form.displayName = "Form";
/**
* This component will emulate the browser's scroll restoration on location
* changes.
*/
function ScrollRestoration(_ref0) {
	let { getKey, storageKey } = _ref0;
	useScrollRestoration({
		getKey,
		storageKey
	});
	return null;
}
ScrollRestoration.displayName = "ScrollRestoration";
var DataRouterHook;
(function(DataRouterHook) {
	DataRouterHook["UseScrollRestoration"] = "useScrollRestoration";
	DataRouterHook["UseSubmit"] = "useSubmit";
	DataRouterHook["UseSubmitFetcher"] = "useSubmitFetcher";
	DataRouterHook["UseFetcher"] = "useFetcher";
	DataRouterHook["useViewTransitionState"] = "useViewTransitionState";
})(DataRouterHook || (DataRouterHook = {}));
var DataRouterStateHook;
(function(DataRouterStateHook) {
	DataRouterStateHook["UseFetcher"] = "useFetcher";
	DataRouterStateHook["UseFetchers"] = "useFetchers";
	DataRouterStateHook["UseScrollRestoration"] = "useScrollRestoration";
})(DataRouterStateHook || (DataRouterStateHook = {}));
function getDataRouterConsoleError(hookName) {
	return hookName + " must be used within a data router.  See https://reactrouter.com/v6/routers/picking-a-router.";
}
function useDataRouterContext(hookName) {
	let ctx = import_react.useContext(DataRouterContext);
	!ctx && invariant(false, getDataRouterConsoleError(hookName));
	return ctx;
}
function useDataRouterState(hookName) {
	let state = import_react.useContext(DataRouterStateContext);
	!state && invariant(false, getDataRouterConsoleError(hookName));
	return state;
}
/**
* Handles the click behavior for router `<Link>` components. This is useful if
* you need to create custom `<Link>` components with the same click behavior we
* use in our exported `<Link>`.
*/
function useLinkClickHandler(to, _temp) {
	let { target, replace: replaceProp, state, preventScrollReset, relative, viewTransition } = _temp === void 0 ? {} : _temp;
	let navigate = useNavigate();
	let location = useLocation();
	let path = useResolvedPath(to, { relative });
	return import_react.useCallback((event) => {
		if (shouldProcessLinkClick(event, target)) {
			event.preventDefault();
			navigate(to, {
				replace: replaceProp !== void 0 ? replaceProp : createPath(location) === createPath(path),
				state,
				preventScrollReset,
				relative,
				viewTransition
			});
		}
	}, [
		location,
		navigate,
		path,
		replaceProp,
		state,
		target,
		to,
		preventScrollReset,
		relative,
		viewTransition
	]);
}
/**
* A convenient wrapper for reading and writing search parameters via the
* URLSearchParams interface.
*/
function useSearchParams(defaultInit) {
	warning(typeof URLSearchParams !== "undefined", "You cannot use the `useSearchParams` hook in a browser that does not support the URLSearchParams API. If you need to support Internet Explorer 11, we recommend you load a polyfill such as https://github.com/ungap/url-search-params.");
	let defaultSearchParamsRef = import_react.useRef(createSearchParams(defaultInit));
	let hasSetSearchParamsRef = import_react.useRef(false);
	let location = useLocation();
	let searchParams = import_react.useMemo(() => getSearchParamsForLocation(location.search, hasSetSearchParamsRef.current ? null : defaultSearchParamsRef.current), [location.search]);
	let navigate = useNavigate();
	return [searchParams, import_react.useCallback((nextInit, navigateOptions) => {
		const newSearchParams = createSearchParams(typeof nextInit === "function" ? nextInit(searchParams) : nextInit);
		hasSetSearchParamsRef.current = true;
		navigate("?" + newSearchParams, navigateOptions);
	}, [navigate, searchParams])];
}
function validateClientSideSubmission() {
	if (typeof document === "undefined") throw new Error("You are calling submit during the server render. Try calling submit within a `useEffect` or callback instead.");
}
var fetcherId = 0;
var getUniqueFetcherId = () => "__" + String(++fetcherId) + "__";
/**
* Returns a function that may be used to programmatically submit a form (or
* some arbitrary data) to the server.
*/
function useSubmit() {
	let { router } = useDataRouterContext(DataRouterHook.UseSubmit);
	let { basename } = import_react.useContext(NavigationContext);
	let currentRouteId = useRouteId();
	return import_react.useCallback(function(target, options) {
		if (options === void 0) options = {};
		validateClientSideSubmission();
		let { action, method, encType, formData, body } = getFormSubmissionInfo(target, basename);
		if (options.navigate === false) {
			let key = options.fetcherKey || getUniqueFetcherId();
			router.fetch(key, currentRouteId, options.action || action, {
				preventScrollReset: options.preventScrollReset,
				formData,
				body,
				formMethod: options.method || method,
				formEncType: options.encType || encType,
				flushSync: options.flushSync
			});
		} else router.navigate(options.action || action, {
			preventScrollReset: options.preventScrollReset,
			formData,
			body,
			formMethod: options.method || method,
			formEncType: options.encType || encType,
			replace: options.replace,
			state: options.state,
			fromRouteId: currentRouteId,
			flushSync: options.flushSync,
			viewTransition: options.viewTransition
		});
	}, [
		router,
		basename,
		currentRouteId
	]);
}
function useFormAction(action, _temp2) {
	let { relative } = _temp2 === void 0 ? {} : _temp2;
	let { basename } = import_react.useContext(NavigationContext);
	let routeContext = import_react.useContext(RouteContext);
	!routeContext && invariant(false, "useFormAction must be used inside a RouteContext");
	let [match] = routeContext.matches.slice(-1);
	let path = _extends({}, useResolvedPath(action ? action : ".", { relative }));
	let location = useLocation();
	if (action == null) {
		path.search = location.search;
		let params = new URLSearchParams(path.search);
		let indexValues = params.getAll("index");
		if (indexValues.some((v) => v === "")) {
			params.delete("index");
			indexValues.filter((v) => v).forEach((v) => params.append("index", v));
			let qs = params.toString();
			path.search = qs ? "?" + qs : "";
		}
	}
	if ((!action || action === ".") && match.route.index) path.search = path.search ? path.search.replace(/^\?/, "?index&") : "?index";
	if (basename !== "/") path.pathname = path.pathname === "/" ? basename : joinPaths([basename, path.pathname]);
	return createPath(path);
}
/**
* Interacts with route loaders and actions without causing a navigation. Great
* for any interaction that stays on the same page.
*/
function useFetcher(_temp3) {
	var _route$matches;
	let { key } = _temp3 === void 0 ? {} : _temp3;
	let { router } = useDataRouterContext(DataRouterHook.UseFetcher);
	let state = useDataRouterState(DataRouterStateHook.UseFetcher);
	let fetcherData = import_react.useContext(FetchersContext);
	let route = import_react.useContext(RouteContext);
	let routeId = (_route$matches = route.matches[route.matches.length - 1]) == null ? void 0 : _route$matches.route.id;
	!fetcherData && invariant(false, "useFetcher must be used inside a FetchersContext");
	!route && invariant(false, "useFetcher must be used inside a RouteContext");
	!(routeId != null) && invariant(false, "useFetcher can only be used on routes that contain a unique \"id\"");
	let defaultKey = useIdImpl ? useIdImpl() : "";
	let [fetcherKey, setFetcherKey] = import_react.useState(key || defaultKey);
	if (key && key !== fetcherKey) setFetcherKey(key);
	else if (!fetcherKey) setFetcherKey(getUniqueFetcherId());
	import_react.useEffect(() => {
		router.getFetcher(fetcherKey);
		return () => {
			router.deleteFetcher(fetcherKey);
		};
	}, [router, fetcherKey]);
	let load = import_react.useCallback((href, opts) => {
		!routeId && invariant(false, "No routeId available for fetcher.load()");
		router.fetch(fetcherKey, routeId, href, opts);
	}, [
		fetcherKey,
		routeId,
		router
	]);
	let submitImpl = useSubmit();
	let submit = import_react.useCallback((target, opts) => {
		submitImpl(target, _extends({}, opts, {
			navigate: false,
			fetcherKey
		}));
	}, [fetcherKey, submitImpl]);
	let FetcherForm = import_react.useMemo(() => {
		let FetcherForm = /*#__PURE__*/ import_react.forwardRef((props, ref) => {
			return /*#__PURE__*/ import_react.createElement(Form, _extends({}, props, {
				navigate: false,
				fetcherKey,
				ref
			}));
		});
		FetcherForm.displayName = "fetcher.Form";
		return FetcherForm;
	}, [fetcherKey]);
	let fetcher = state.fetchers.get(fetcherKey) || IDLE_FETCHER;
	let data = fetcherData.get(fetcherKey);
	return import_react.useMemo(() => _extends({
		Form: FetcherForm,
		submit,
		load
	}, fetcher, { data }), [
		FetcherForm,
		submit,
		load,
		fetcher,
		data
	]);
}
/**
* Provides all fetchers currently on the page. Useful for layouts and parent
* routes that need to provide pending/optimistic UI regarding the fetch.
*/
function useFetchers() {
	let state = useDataRouterState(DataRouterStateHook.UseFetchers);
	return Array.from(state.fetchers.entries()).map((_ref1) => {
		let [key, fetcher] = _ref1;
		return _extends({}, fetcher, { key });
	});
}
var SCROLL_RESTORATION_STORAGE_KEY = "react-router-scroll-positions";
var savedScrollPositions = {};
/**
* When rendered inside a RouterProvider, will restore scroll positions on navigations
*/
function useScrollRestoration(_temp4) {
	let { getKey, storageKey } = _temp4 === void 0 ? {} : _temp4;
	let { router } = useDataRouterContext(DataRouterHook.UseScrollRestoration);
	let { restoreScrollPosition, preventScrollReset } = useDataRouterState(DataRouterStateHook.UseScrollRestoration);
	let { basename } = import_react.useContext(NavigationContext);
	let location = useLocation();
	let matches = useMatches();
	let navigation = useNavigation();
	import_react.useEffect(() => {
		window.history.scrollRestoration = "manual";
		return () => {
			window.history.scrollRestoration = "auto";
		};
	}, []);
	usePageHide(import_react.useCallback(() => {
		if (navigation.state === "idle") {
			let key = (getKey ? getKey(location, matches) : null) || location.key;
			savedScrollPositions[key] = window.scrollY;
		}
		try {
			sessionStorage.setItem(storageKey || SCROLL_RESTORATION_STORAGE_KEY, JSON.stringify(savedScrollPositions));
		} catch (error) {
			warning(false, "Failed to save scroll positions in sessionStorage, <ScrollRestoration /> will not work properly (" + error + ").");
		}
		window.history.scrollRestoration = "auto";
	}, [
		storageKey,
		getKey,
		navigation.state,
		location,
		matches
	]));
	if (typeof document !== "undefined") {
		import_react.useLayoutEffect(() => {
			try {
				let sessionPositions = sessionStorage.getItem(storageKey || SCROLL_RESTORATION_STORAGE_KEY);
				if (sessionPositions) savedScrollPositions = JSON.parse(sessionPositions);
			} catch (e) {}
		}, [storageKey]);
		import_react.useLayoutEffect(() => {
			let getKeyWithoutBasename = getKey && basename !== "/" ? (location, matches) => getKey(_extends({}, location, { pathname: stripBasename(location.pathname, basename) || location.pathname }), matches) : getKey;
			let disableScrollRestoration = router == null ? void 0 : router.enableScrollRestoration(savedScrollPositions, () => window.scrollY, getKeyWithoutBasename);
			return () => disableScrollRestoration && disableScrollRestoration();
		}, [
			router,
			basename,
			getKey
		]);
		import_react.useLayoutEffect(() => {
			if (restoreScrollPosition === false) return;
			if (typeof restoreScrollPosition === "number") {
				window.scrollTo(0, restoreScrollPosition);
				return;
			}
			if (location.hash) {
				let el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
				if (el) {
					el.scrollIntoView();
					return;
				}
			}
			if (preventScrollReset === true) return;
			window.scrollTo(0, 0);
		}, [
			location,
			restoreScrollPosition,
			preventScrollReset
		]);
	}
}
/**
* Setup a callback to be fired on the window's `beforeunload` event. This is
* useful for saving some data to `window.localStorage` just before the page
* refreshes.
*
* Note: The `callback` argument should be a function created with
* `React.useCallback()`.
*/
function useBeforeUnload(callback, options) {
	let { capture } = options || {};
	import_react.useEffect(() => {
		let opts = capture != null ? { capture } : void 0;
		window.addEventListener("beforeunload", callback, opts);
		return () => {
			window.removeEventListener("beforeunload", callback, opts);
		};
	}, [callback, capture]);
}
/**
* Setup a callback to be fired on the window's `pagehide` event. This is
* useful for saving some data to `window.localStorage` just before the page
* refreshes.  This event is better supported than beforeunload across browsers.
*
* Note: The `callback` argument should be a function created with
* `React.useCallback()`.
*/
function usePageHide(callback, options) {
	let { capture } = options || {};
	import_react.useEffect(() => {
		let opts = capture != null ? { capture } : void 0;
		window.addEventListener("pagehide", callback, opts);
		return () => {
			window.removeEventListener("pagehide", callback, opts);
		};
	}, [callback, capture]);
}
/**
* Wrapper around useBlocker to show a window.confirm prompt to users instead
* of building a custom UI with useBlocker.
*
* Warning: This has *a lot of rough edges* and behaves very differently (and
* very incorrectly in some cases) across browsers if user click addition
* back/forward navigations while the confirm is open.  Use at your own risk.
*/
function usePrompt(_ref10) {
	let { when, message } = _ref10;
	let blocker = useBlocker(when);
	import_react.useEffect(() => {
		if (blocker.state === "blocked") if (window.confirm(message)) setTimeout(blocker.proceed, 0);
		else blocker.reset();
	}, [blocker, message]);
	import_react.useEffect(() => {
		if (blocker.state === "blocked" && !when) blocker.reset();
	}, [blocker, when]);
}
/**
* Return a boolean indicating if there is an active view transition to the
* given href.  You can use this value to render CSS classes or viewTransitionName
* styles onto your elements
*
* @param href The destination href
* @param [opts.relative] Relative routing type ("route" | "path")
*/
function useViewTransitionState(to, opts) {
	if (opts === void 0) opts = {};
	let vtContext = import_react.useContext(ViewTransitionContext);
	!(vtContext != null) && invariant(false, "`useViewTransitionState` must be used within `react-router-dom`'s `RouterProvider`.  Did you accidentally import `RouterProvider` from `react-router`?");
	let { basename } = useDataRouterContext(DataRouterHook.useViewTransitionState);
	let path = useResolvedPath(to, { relative: opts.relative });
	if (!vtContext.isTransitioning) return false;
	let currentPath = stripBasename(vtContext.currentLocation.pathname, basename) || vtContext.currentLocation.pathname;
	let nextPath = stripBasename(vtContext.nextLocation.pathname, basename) || vtContext.nextLocation.pathname;
	return matchPath(path.pathname, nextPath) != null || matchPath(path.pathname, currentPath) != null;
}
//#endregion
export { AbortedDeferredError, Await, BrowserRouter, Form, HashRouter, Link, MemoryRouter, NavLink, Navigate, Action as NavigationType, Outlet, Route, Router, RouterProvider, Routes, ScrollRestoration, DataRouterContext as UNSAFE_DataRouterContext, DataRouterStateContext as UNSAFE_DataRouterStateContext, ErrorResponseImpl as UNSAFE_ErrorResponseImpl, FetchersContext as UNSAFE_FetchersContext, LocationContext as UNSAFE_LocationContext, NavigationContext as UNSAFE_NavigationContext, RouteContext as UNSAFE_RouteContext, ViewTransitionContext as UNSAFE_ViewTransitionContext, useRouteId as UNSAFE_useRouteId, useScrollRestoration as UNSAFE_useScrollRestoration, createBrowserRouter, createHashRouter, createMemoryRouter, createPath, createRoutesFromChildren, createRoutesFromChildren as createRoutesFromElements, createSearchParams, defer, generatePath, isRouteErrorResponse, json, matchPath, matchRoutes, parsePath, redirect, redirectDocument, renderMatches, replace, resolvePath, HistoryRouter as unstable_HistoryRouter, usePrompt as unstable_usePrompt, useActionData, useAsyncError, useAsyncValue, useBeforeUnload, useBlocker, useFetcher, useFetchers, useFormAction, useHref, useInRouterContext, useLinkClickHandler, useLoaderData, useLocation, useMatch, useMatches, useNavigate, useNavigation, useNavigationType, useOutlet, useOutletContext, useParams, useResolvedPath, useRevalidator, useRouteError, useRouteLoaderData, useRoutes, useSearchParams, useSubmit, useViewTransitionState };

//# sourceMappingURL=react-router-dom.js.map