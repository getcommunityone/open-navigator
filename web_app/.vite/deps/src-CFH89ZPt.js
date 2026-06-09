import { n as __esmMin } from "./chunk-_TIqcEvS.js";
//#region node_modules/d3-selection/src/namespaces.js
var xhtml, namespaces_default;
var init_namespaces = __esmMin((() => {
	xhtml = "http://www.w3.org/1999/xhtml";
	namespaces_default = {
		svg: "http://www.w3.org/2000/svg",
		xhtml,
		xlink: "http://www.w3.org/1999/xlink",
		xml: "http://www.w3.org/XML/1998/namespace",
		xmlns: "http://www.w3.org/2000/xmlns/"
	};
}));
//#endregion
//#region node_modules/d3-selection/src/namespace.js
function namespace_default(name) {
	var prefix = name += "", i = prefix.indexOf(":");
	if (i >= 0 && (prefix = name.slice(0, i)) !== "xmlns") name = name.slice(i + 1);
	return namespaces_default.hasOwnProperty(prefix) ? {
		space: namespaces_default[prefix],
		local: name
	} : name;
}
var init_namespace = __esmMin((() => {
	init_namespaces();
}));
//#endregion
//#region node_modules/d3-selection/src/creator.js
function creatorInherit(name) {
	return function() {
		var document = this.ownerDocument, uri = this.namespaceURI;
		return uri === "http://www.w3.org/1999/xhtml" && document.documentElement.namespaceURI === "http://www.w3.org/1999/xhtml" ? document.createElement(name) : document.createElementNS(uri, name);
	};
}
function creatorFixed(fullname) {
	return function() {
		return this.ownerDocument.createElementNS(fullname.space, fullname.local);
	};
}
function creator_default(name) {
	var fullname = namespace_default(name);
	return (fullname.local ? creatorFixed : creatorInherit)(fullname);
}
var init_creator = __esmMin((() => {
	init_namespace();
	init_namespaces();
}));
//#endregion
//#region node_modules/d3-selection/src/selector.js
function none() {}
function selector_default(selector) {
	return selector == null ? none : function() {
		return this.querySelector(selector);
	};
}
var init_selector = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/select.js
function select_default$1(select) {
	if (typeof select !== "function") select = selector_default(select);
	for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) for (var group = groups[j], n = group.length, subgroup = subgroups[j] = new Array(n), node, subnode, i = 0; i < n; ++i) if ((node = group[i]) && (subnode = select.call(node, node.__data__, i, group))) {
		if ("__data__" in node) subnode.__data__ = node.__data__;
		subgroup[i] = subnode;
	}
	return new Selection(subgroups, this._parents);
}
var init_select$1 = __esmMin((() => {
	init_selection();
	init_selector();
}));
//#endregion
//#region node_modules/d3-selection/src/array.js
function array(x) {
	return x == null ? [] : Array.isArray(x) ? x : Array.from(x);
}
var init_array = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selectorAll.js
function empty() {
	return [];
}
function selectorAll_default(selector) {
	return selector == null ? empty : function() {
		return this.querySelectorAll(selector);
	};
}
var init_selectorAll = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/selectAll.js
function arrayAll(select) {
	return function() {
		return array(select.apply(this, arguments));
	};
}
function selectAll_default$1(select) {
	if (typeof select === "function") select = arrayAll(select);
	else select = selectorAll_default(select);
	for (var groups = this._groups, m = groups.length, subgroups = [], parents = [], j = 0; j < m; ++j) for (var group = groups[j], n = group.length, node, i = 0; i < n; ++i) if (node = group[i]) {
		subgroups.push(select.call(node, node.__data__, i, group));
		parents.push(node);
	}
	return new Selection(subgroups, parents);
}
var init_selectAll$1 = __esmMin((() => {
	init_selection();
	init_array();
	init_selectorAll();
}));
//#endregion
//#region node_modules/d3-selection/src/matcher.js
function matcher_default(selector) {
	return function() {
		return this.matches(selector);
	};
}
function childMatcher(selector) {
	return function(node) {
		return node.matches(selector);
	};
}
var init_matcher = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/selectChild.js
function childFind(match) {
	return function() {
		return find.call(this.children, match);
	};
}
function childFirst() {
	return this.firstElementChild;
}
function selectChild_default(match) {
	return this.select(match == null ? childFirst : childFind(typeof match === "function" ? match : childMatcher(match)));
}
var find;
var init_selectChild = __esmMin((() => {
	init_matcher();
	find = Array.prototype.find;
}));
//#endregion
//#region node_modules/d3-selection/src/selection/selectChildren.js
function children() {
	return Array.from(this.children);
}
function childrenFilter(match) {
	return function() {
		return filter.call(this.children, match);
	};
}
function selectChildren_default(match) {
	return this.selectAll(match == null ? children : childrenFilter(typeof match === "function" ? match : childMatcher(match)));
}
var filter;
var init_selectChildren = __esmMin((() => {
	init_matcher();
	filter = Array.prototype.filter;
}));
//#endregion
//#region node_modules/d3-selection/src/selection/filter.js
function filter_default(match) {
	if (typeof match !== "function") match = matcher_default(match);
	for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) for (var group = groups[j], n = group.length, subgroup = subgroups[j] = [], node, i = 0; i < n; ++i) if ((node = group[i]) && match.call(node, node.__data__, i, group)) subgroup.push(node);
	return new Selection(subgroups, this._parents);
}
var init_filter = __esmMin((() => {
	init_selection();
	init_matcher();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/sparse.js
function sparse_default(update) {
	return new Array(update.length);
}
var init_sparse = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/enter.js
function enter_default() {
	return new Selection(this._enter || this._groups.map(sparse_default), this._parents);
}
function EnterNode(parent, datum) {
	this.ownerDocument = parent.ownerDocument;
	this.namespaceURI = parent.namespaceURI;
	this._next = null;
	this._parent = parent;
	this.__data__ = datum;
}
var init_enter = __esmMin((() => {
	init_sparse();
	init_selection();
	EnterNode.prototype = {
		constructor: EnterNode,
		appendChild: function(child) {
			return this._parent.insertBefore(child, this._next);
		},
		insertBefore: function(child, next) {
			return this._parent.insertBefore(child, next);
		},
		querySelector: function(selector) {
			return this._parent.querySelector(selector);
		},
		querySelectorAll: function(selector) {
			return this._parent.querySelectorAll(selector);
		}
	};
}));
//#endregion
//#region node_modules/d3-selection/src/constant.js
function constant_default(x) {
	return function() {
		return x;
	};
}
var init_constant = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/data.js
function bindIndex(parent, group, enter, update, exit, data) {
	var i = 0, node, groupLength = group.length, dataLength = data.length;
	for (; i < dataLength; ++i) if (node = group[i]) {
		node.__data__ = data[i];
		update[i] = node;
	} else enter[i] = new EnterNode(parent, data[i]);
	for (; i < groupLength; ++i) if (node = group[i]) exit[i] = node;
}
function bindKey(parent, group, enter, update, exit, data, key) {
	var i, node, nodeByKeyValue = /* @__PURE__ */ new Map(), groupLength = group.length, dataLength = data.length, keyValues = new Array(groupLength), keyValue;
	for (i = 0; i < groupLength; ++i) if (node = group[i]) {
		keyValues[i] = keyValue = key.call(node, node.__data__, i, group) + "";
		if (nodeByKeyValue.has(keyValue)) exit[i] = node;
		else nodeByKeyValue.set(keyValue, node);
	}
	for (i = 0; i < dataLength; ++i) {
		keyValue = key.call(parent, data[i], i, data) + "";
		if (node = nodeByKeyValue.get(keyValue)) {
			update[i] = node;
			node.__data__ = data[i];
			nodeByKeyValue.delete(keyValue);
		} else enter[i] = new EnterNode(parent, data[i]);
	}
	for (i = 0; i < groupLength; ++i) if ((node = group[i]) && nodeByKeyValue.get(keyValues[i]) === node) exit[i] = node;
}
function datum(node) {
	return node.__data__;
}
function data_default(value, key) {
	if (!arguments.length) return Array.from(this, datum);
	var bind = key ? bindKey : bindIndex, parents = this._parents, groups = this._groups;
	if (typeof value !== "function") value = constant_default(value);
	for (var m = groups.length, update = new Array(m), enter = new Array(m), exit = new Array(m), j = 0; j < m; ++j) {
		var parent = parents[j], group = groups[j], groupLength = group.length, data = arraylike(value.call(parent, parent && parent.__data__, j, parents)), dataLength = data.length, enterGroup = enter[j] = new Array(dataLength), updateGroup = update[j] = new Array(dataLength);
		bind(parent, group, enterGroup, updateGroup, exit[j] = new Array(groupLength), data, key);
		for (var i0 = 0, i1 = 0, previous, next; i0 < dataLength; ++i0) if (previous = enterGroup[i0]) {
			if (i0 >= i1) i1 = i0 + 1;
			while (!(next = updateGroup[i1]) && ++i1 < dataLength);
			previous._next = next || null;
		}
	}
	update = new Selection(update, parents);
	update._enter = enter;
	update._exit = exit;
	return update;
}
function arraylike(data) {
	return typeof data === "object" && "length" in data ? data : Array.from(data);
}
var init_data = __esmMin((() => {
	init_selection();
	init_enter();
	init_constant();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/exit.js
function exit_default() {
	return new Selection(this._exit || this._groups.map(sparse_default), this._parents);
}
var init_exit = __esmMin((() => {
	init_sparse();
	init_selection();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/join.js
function join_default(onenter, onupdate, onexit) {
	var enter = this.enter(), update = this, exit = this.exit();
	if (typeof onenter === "function") {
		enter = onenter(enter);
		if (enter) enter = enter.selection();
	} else enter = enter.append(onenter + "");
	if (onupdate != null) {
		update = onupdate(update);
		if (update) update = update.selection();
	}
	if (onexit == null) exit.remove();
	else onexit(exit);
	return enter && update ? enter.merge(update).order() : update;
}
var init_join = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/merge.js
function merge_default(context) {
	var selection = context.selection ? context.selection() : context;
	for (var groups0 = this._groups, groups1 = selection._groups, m0 = groups0.length, m1 = groups1.length, m = Math.min(m0, m1), merges = new Array(m0), j = 0; j < m; ++j) for (var group0 = groups0[j], group1 = groups1[j], n = group0.length, merge = merges[j] = new Array(n), node, i = 0; i < n; ++i) if (node = group0[i] || group1[i]) merge[i] = node;
	for (; j < m0; ++j) merges[j] = groups0[j];
	return new Selection(merges, this._parents);
}
var init_merge = __esmMin((() => {
	init_selection();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/order.js
function order_default() {
	for (var groups = this._groups, j = -1, m = groups.length; ++j < m;) for (var group = groups[j], i = group.length - 1, next = group[i], node; --i >= 0;) if (node = group[i]) {
		if (next && node.compareDocumentPosition(next) ^ 4) next.parentNode.insertBefore(node, next);
		next = node;
	}
	return this;
}
var init_order = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/sort.js
function sort_default(compare) {
	if (!compare) compare = ascending;
	function compareNode(a, b) {
		return a && b ? compare(a.__data__, b.__data__) : !a - !b;
	}
	for (var groups = this._groups, m = groups.length, sortgroups = new Array(m), j = 0; j < m; ++j) {
		for (var group = groups[j], n = group.length, sortgroup = sortgroups[j] = new Array(n), node, i = 0; i < n; ++i) if (node = group[i]) sortgroup[i] = node;
		sortgroup.sort(compareNode);
	}
	return new Selection(sortgroups, this._parents).order();
}
function ascending(a, b) {
	return a < b ? -1 : a > b ? 1 : a >= b ? 0 : NaN;
}
var init_sort = __esmMin((() => {
	init_selection();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/call.js
function call_default() {
	var callback = arguments[0];
	arguments[0] = this;
	callback.apply(null, arguments);
	return this;
}
var init_call = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/nodes.js
function nodes_default() {
	return Array.from(this);
}
var init_nodes = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/node.js
function node_default() {
	for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) for (var group = groups[j], i = 0, n = group.length; i < n; ++i) {
		var node = group[i];
		if (node) return node;
	}
	return null;
}
var init_node = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/size.js
function size_default() {
	let size = 0;
	for (const node of this) ++size;
	return size;
}
var init_size = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/empty.js
function empty_default() {
	return !this.node();
}
var init_empty = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/each.js
function each_default(callback) {
	for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) for (var group = groups[j], i = 0, n = group.length, node; i < n; ++i) if (node = group[i]) callback.call(node, node.__data__, i, group);
	return this;
}
var init_each = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/attr.js
function attrRemove(name) {
	return function() {
		this.removeAttribute(name);
	};
}
function attrRemoveNS(fullname) {
	return function() {
		this.removeAttributeNS(fullname.space, fullname.local);
	};
}
function attrConstant(name, value) {
	return function() {
		this.setAttribute(name, value);
	};
}
function attrConstantNS(fullname, value) {
	return function() {
		this.setAttributeNS(fullname.space, fullname.local, value);
	};
}
function attrFunction(name, value) {
	return function() {
		var v = value.apply(this, arguments);
		if (v == null) this.removeAttribute(name);
		else this.setAttribute(name, v);
	};
}
function attrFunctionNS(fullname, value) {
	return function() {
		var v = value.apply(this, arguments);
		if (v == null) this.removeAttributeNS(fullname.space, fullname.local);
		else this.setAttributeNS(fullname.space, fullname.local, v);
	};
}
function attr_default(name, value) {
	var fullname = namespace_default(name);
	if (arguments.length < 2) {
		var node = this.node();
		return fullname.local ? node.getAttributeNS(fullname.space, fullname.local) : node.getAttribute(fullname);
	}
	return this.each((value == null ? fullname.local ? attrRemoveNS : attrRemove : typeof value === "function" ? fullname.local ? attrFunctionNS : attrFunction : fullname.local ? attrConstantNS : attrConstant)(fullname, value));
}
var init_attr = __esmMin((() => {
	init_namespace();
}));
//#endregion
//#region node_modules/d3-selection/src/window.js
function window_default(node) {
	return node.ownerDocument && node.ownerDocument.defaultView || node.document && node || node.defaultView;
}
var init_window = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/style.js
function styleRemove(name) {
	return function() {
		this.style.removeProperty(name);
	};
}
function styleConstant(name, value, priority) {
	return function() {
		this.style.setProperty(name, value, priority);
	};
}
function styleFunction(name, value, priority) {
	return function() {
		var v = value.apply(this, arguments);
		if (v == null) this.style.removeProperty(name);
		else this.style.setProperty(name, v, priority);
	};
}
function style_default(name, value, priority) {
	return arguments.length > 1 ? this.each((value == null ? styleRemove : typeof value === "function" ? styleFunction : styleConstant)(name, value, priority == null ? "" : priority)) : styleValue(this.node(), name);
}
function styleValue(node, name) {
	return node.style.getPropertyValue(name) || window_default(node).getComputedStyle(node, null).getPropertyValue(name);
}
var init_style = __esmMin((() => {
	init_window();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/property.js
function propertyRemove(name) {
	return function() {
		delete this[name];
	};
}
function propertyConstant(name, value) {
	return function() {
		this[name] = value;
	};
}
function propertyFunction(name, value) {
	return function() {
		var v = value.apply(this, arguments);
		if (v == null) delete this[name];
		else this[name] = v;
	};
}
function property_default(name, value) {
	return arguments.length > 1 ? this.each((value == null ? propertyRemove : typeof value === "function" ? propertyFunction : propertyConstant)(name, value)) : this.node()[name];
}
var init_property = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/classed.js
function classArray(string) {
	return string.trim().split(/^|\s+/);
}
function classList(node) {
	return node.classList || new ClassList(node);
}
function ClassList(node) {
	this._node = node;
	this._names = classArray(node.getAttribute("class") || "");
}
function classedAdd(node, names) {
	var list = classList(node), i = -1, n = names.length;
	while (++i < n) list.add(names[i]);
}
function classedRemove(node, names) {
	var list = classList(node), i = -1, n = names.length;
	while (++i < n) list.remove(names[i]);
}
function classedTrue(names) {
	return function() {
		classedAdd(this, names);
	};
}
function classedFalse(names) {
	return function() {
		classedRemove(this, names);
	};
}
function classedFunction(names, value) {
	return function() {
		(value.apply(this, arguments) ? classedAdd : classedRemove)(this, names);
	};
}
function classed_default(name, value) {
	var names = classArray(name + "");
	if (arguments.length < 2) {
		var list = classList(this.node()), i = -1, n = names.length;
		while (++i < n) if (!list.contains(names[i])) return false;
		return true;
	}
	return this.each((typeof value === "function" ? classedFunction : value ? classedTrue : classedFalse)(names, value));
}
var init_classed = __esmMin((() => {
	ClassList.prototype = {
		add: function(name) {
			if (this._names.indexOf(name) < 0) {
				this._names.push(name);
				this._node.setAttribute("class", this._names.join(" "));
			}
		},
		remove: function(name) {
			var i = this._names.indexOf(name);
			if (i >= 0) {
				this._names.splice(i, 1);
				this._node.setAttribute("class", this._names.join(" "));
			}
		},
		contains: function(name) {
			return this._names.indexOf(name) >= 0;
		}
	};
}));
//#endregion
//#region node_modules/d3-selection/src/selection/text.js
function textRemove() {
	this.textContent = "";
}
function textConstant(value) {
	return function() {
		this.textContent = value;
	};
}
function textFunction(value) {
	return function() {
		var v = value.apply(this, arguments);
		this.textContent = v == null ? "" : v;
	};
}
function text_default(value) {
	return arguments.length ? this.each(value == null ? textRemove : (typeof value === "function" ? textFunction : textConstant)(value)) : this.node().textContent;
}
var init_text = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/html.js
function htmlRemove() {
	this.innerHTML = "";
}
function htmlConstant(value) {
	return function() {
		this.innerHTML = value;
	};
}
function htmlFunction(value) {
	return function() {
		var v = value.apply(this, arguments);
		this.innerHTML = v == null ? "" : v;
	};
}
function html_default(value) {
	return arguments.length ? this.each(value == null ? htmlRemove : (typeof value === "function" ? htmlFunction : htmlConstant)(value)) : this.node().innerHTML;
}
var init_html = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/raise.js
function raise() {
	if (this.nextSibling) this.parentNode.appendChild(this);
}
function raise_default() {
	return this.each(raise);
}
var init_raise = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/lower.js
function lower() {
	if (this.previousSibling) this.parentNode.insertBefore(this, this.parentNode.firstChild);
}
function lower_default() {
	return this.each(lower);
}
var init_lower = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/append.js
function append_default(name) {
	var create = typeof name === "function" ? name : creator_default(name);
	return this.select(function() {
		return this.appendChild(create.apply(this, arguments));
	});
}
var init_append = __esmMin((() => {
	init_creator();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/insert.js
function constantNull() {
	return null;
}
function insert_default(name, before) {
	var create = typeof name === "function" ? name : creator_default(name), select = before == null ? constantNull : typeof before === "function" ? before : selector_default(before);
	return this.select(function() {
		return this.insertBefore(create.apply(this, arguments), select.apply(this, arguments) || null);
	});
}
var init_insert = __esmMin((() => {
	init_creator();
	init_selector();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/remove.js
function remove() {
	var parent = this.parentNode;
	if (parent) parent.removeChild(this);
}
function remove_default() {
	return this.each(remove);
}
var init_remove = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/clone.js
function selection_cloneShallow() {
	var clone = this.cloneNode(false), parent = this.parentNode;
	return parent ? parent.insertBefore(clone, this.nextSibling) : clone;
}
function selection_cloneDeep() {
	var clone = this.cloneNode(true), parent = this.parentNode;
	return parent ? parent.insertBefore(clone, this.nextSibling) : clone;
}
function clone_default(deep) {
	return this.select(deep ? selection_cloneDeep : selection_cloneShallow);
}
var init_clone = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/datum.js
function datum_default(value) {
	return arguments.length ? this.property("__data__", value) : this.node().__data__;
}
var init_datum = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/on.js
function contextListener(listener) {
	return function(event) {
		listener.call(this, event, this.__data__);
	};
}
function parseTypenames(typenames) {
	return typenames.trim().split(/^|\s+/).map(function(t) {
		var name = "", i = t.indexOf(".");
		if (i >= 0) name = t.slice(i + 1), t = t.slice(0, i);
		return {
			type: t,
			name
		};
	});
}
function onRemove(typename) {
	return function() {
		var on = this.__on;
		if (!on) return;
		for (var j = 0, i = -1, m = on.length, o; j < m; ++j) if (o = on[j], (!typename.type || o.type === typename.type) && o.name === typename.name) this.removeEventListener(o.type, o.listener, o.options);
		else on[++i] = o;
		if (++i) on.length = i;
		else delete this.__on;
	};
}
function onAdd(typename, value, options) {
	return function() {
		var on = this.__on, o, listener = contextListener(value);
		if (on) {
			for (var j = 0, m = on.length; j < m; ++j) if ((o = on[j]).type === typename.type && o.name === typename.name) {
				this.removeEventListener(o.type, o.listener, o.options);
				this.addEventListener(o.type, o.listener = listener, o.options = options);
				o.value = value;
				return;
			}
		}
		this.addEventListener(typename.type, listener, options);
		o = {
			type: typename.type,
			name: typename.name,
			value,
			listener,
			options
		};
		if (!on) this.__on = [o];
		else on.push(o);
	};
}
function on_default(typename, value, options) {
	var typenames = parseTypenames(typename + ""), i, n = typenames.length, t;
	if (arguments.length < 2) {
		var on = this.node().__on;
		if (on) {
			for (var j = 0, m = on.length, o; j < m; ++j) for (i = 0, o = on[j]; i < n; ++i) if ((t = typenames[i]).type === o.type && t.name === o.name) return o.value;
		}
		return;
	}
	on = value ? onAdd : onRemove;
	for (i = 0; i < n; ++i) this.each(on(typenames[i], value, options));
	return this;
}
var init_on = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/dispatch.js
function dispatchEvent(node, type, params) {
	var window = window_default(node), event = window.CustomEvent;
	if (typeof event === "function") event = new event(type, params);
	else {
		event = window.document.createEvent("Event");
		if (params) event.initEvent(type, params.bubbles, params.cancelable), event.detail = params.detail;
		else event.initEvent(type, false, false);
	}
	node.dispatchEvent(event);
}
function dispatchConstant(type, params) {
	return function() {
		return dispatchEvent(this, type, params);
	};
}
function dispatchFunction(type, params) {
	return function() {
		return dispatchEvent(this, type, params.apply(this, arguments));
	};
}
function dispatch_default(type, params) {
	return this.each((typeof params === "function" ? dispatchFunction : dispatchConstant)(type, params));
}
var init_dispatch = __esmMin((() => {
	init_window();
}));
//#endregion
//#region node_modules/d3-selection/src/selection/iterator.js
function* iterator_default() {
	for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) for (var group = groups[j], i = 0, n = group.length, node; i < n; ++i) if (node = group[i]) yield node;
}
var init_iterator = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/selection/index.js
function Selection(groups, parents) {
	this._groups = groups;
	this._parents = parents;
}
function selection() {
	return new Selection([[document.documentElement]], root);
}
function selection_selection() {
	return this;
}
var root;
var init_selection = __esmMin((() => {
	init_select$1();
	init_selectAll$1();
	init_selectChild();
	init_selectChildren();
	init_filter();
	init_data();
	init_enter();
	init_exit();
	init_join();
	init_merge();
	init_order();
	init_sort();
	init_call();
	init_nodes();
	init_node();
	init_size();
	init_empty();
	init_each();
	init_attr();
	init_style();
	init_property();
	init_classed();
	init_text();
	init_html();
	init_raise();
	init_lower();
	init_append();
	init_insert();
	init_remove();
	init_clone();
	init_datum();
	init_on();
	init_dispatch();
	init_iterator();
	root = [null];
	Selection.prototype = selection.prototype = {
		constructor: Selection,
		select: select_default$1,
		selectAll: selectAll_default$1,
		selectChild: selectChild_default,
		selectChildren: selectChildren_default,
		filter: filter_default,
		data: data_default,
		enter: enter_default,
		exit: exit_default,
		join: join_default,
		merge: merge_default,
		selection: selection_selection,
		order: order_default,
		sort: sort_default,
		call: call_default,
		nodes: nodes_default,
		node: node_default,
		size: size_default,
		empty: empty_default,
		each: each_default,
		attr: attr_default,
		style: style_default,
		property: property_default,
		classed: classed_default,
		text: text_default,
		html: html_default,
		raise: raise_default,
		lower: lower_default,
		append: append_default,
		insert: insert_default,
		remove: remove_default,
		clone: clone_default,
		datum: datum_default,
		on: on_default,
		dispatch: dispatch_default,
		[Symbol.iterator]: iterator_default
	};
}));
//#endregion
//#region node_modules/d3-selection/src/select.js
function select_default(selector) {
	return typeof selector === "string" ? new Selection([[document.querySelector(selector)]], [document.documentElement]) : new Selection([[selector]], root);
}
var init_select = __esmMin((() => {
	init_selection();
}));
//#endregion
//#region node_modules/d3-selection/src/create.js
function create_default(name) {
	return select_default(creator_default(name).call(document.documentElement));
}
var init_create = __esmMin((() => {
	init_creator();
	init_select();
}));
//#endregion
//#region node_modules/d3-selection/src/local.js
function local() {
	return new Local();
}
function Local() {
	this._ = "@" + (++nextId).toString(36);
}
var nextId;
var init_local = __esmMin((() => {
	nextId = 0;
	Local.prototype = local.prototype = {
		constructor: Local,
		get: function(node) {
			var id = this._;
			while (!(id in node)) if (!(node = node.parentNode)) return;
			return node[id];
		},
		set: function(node, value) {
			return node[this._] = value;
		},
		remove: function(node) {
			return this._ in node && delete node[this._];
		},
		toString: function() {
			return this._;
		}
	};
}));
//#endregion
//#region node_modules/d3-selection/src/sourceEvent.js
function sourceEvent_default(event) {
	let sourceEvent;
	while (sourceEvent = event.sourceEvent) event = sourceEvent;
	return event;
}
var init_sourceEvent = __esmMin((() => {}));
//#endregion
//#region node_modules/d3-selection/src/pointer.js
function pointer_default(event, node) {
	event = sourceEvent_default(event);
	if (node === void 0) node = event.currentTarget;
	if (node) {
		var svg = node.ownerSVGElement || node;
		if (svg.createSVGPoint) {
			var point = svg.createSVGPoint();
			point.x = event.clientX, point.y = event.clientY;
			point = point.matrixTransform(node.getScreenCTM().inverse());
			return [point.x, point.y];
		}
		if (node.getBoundingClientRect) {
			var rect = node.getBoundingClientRect();
			return [event.clientX - rect.left - node.clientLeft, event.clientY - rect.top - node.clientTop];
		}
	}
	return [event.pageX, event.pageY];
}
var init_pointer = __esmMin((() => {
	init_sourceEvent();
}));
//#endregion
//#region node_modules/d3-selection/src/pointers.js
function pointers_default(events, node) {
	if (events.target) {
		events = sourceEvent_default(events);
		if (node === void 0) node = events.currentTarget;
		events = events.touches || [events];
	}
	return Array.from(events, (event) => pointer_default(event, node));
}
var init_pointers = __esmMin((() => {
	init_pointer();
	init_sourceEvent();
}));
//#endregion
//#region node_modules/d3-selection/src/selectAll.js
function selectAll_default(selector) {
	return typeof selector === "string" ? new Selection([document.querySelectorAll(selector)], [document.documentElement]) : new Selection([array(selector)], root);
}
var init_selectAll = __esmMin((() => {
	init_array();
	init_selection();
}));
//#endregion
//#region node_modules/d3-selection/src/index.js
var init_src = __esmMin((() => {
	init_create();
	init_creator();
	init_local();
	init_matcher();
	init_namespace();
	init_namespaces();
	init_pointer();
	init_pointers();
	init_select();
	init_selectAll();
	init_selection();
	init_selector();
	init_selectorAll();
	init_style();
	init_window();
}));
//#endregion
export { init_namespaces as A, selectorAll_default as C, init_creator as D, creator_default as E, init_namespace as O, init_selectorAll as S, selector_default as T, styleValue as _, pointers_default as a, init_matcher as b, init_local as c, init_create as d, init_select as f, init_style as g, selection as h, init_pointers as i, namespaces_default as j, namespace_default as k, local as l, init_selection as m, init_selectAll as n, init_pointer as o, select_default as p, selectAll_default as r, pointer_default as s, init_src as t, create_default as u, init_window as v, init_selector as w, matcher_default as x, window_default as y };

//# sourceMappingURL=src-CFH89ZPt.js.map