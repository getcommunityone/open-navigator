import { n as __esmMin, r as __exportAll } from "./chunk-_TIqcEvS.js";
//#region node_modules/topojson-client/src/identity.js
function identity_default(x) {
	return x;
}
var init_identity = __esmMin((() => {}));
//#endregion
//#region node_modules/topojson-client/src/transform.js
function transform_default(transform) {
	if (transform == null) return identity_default;
	var x0, y0, kx = transform.scale[0], ky = transform.scale[1], dx = transform.translate[0], dy = transform.translate[1];
	return function(input, i) {
		if (!i) x0 = y0 = 0;
		var j = 2, n = input.length, output = new Array(n);
		output[0] = (x0 += input[0]) * kx + dx;
		output[1] = (y0 += input[1]) * ky + dy;
		while (j < n) output[j] = input[j], ++j;
		return output;
	};
}
var init_transform = __esmMin((() => {
	init_identity();
}));
//#endregion
//#region node_modules/topojson-client/src/bbox.js
function bbox_default(topology) {
	var t = transform_default(topology.transform), key, x0 = Infinity, y0 = x0, x1 = -x0, y1 = -x0;
	function bboxPoint(p) {
		p = t(p);
		if (p[0] < x0) x0 = p[0];
		if (p[0] > x1) x1 = p[0];
		if (p[1] < y0) y0 = p[1];
		if (p[1] > y1) y1 = p[1];
	}
	function bboxGeometry(o) {
		switch (o.type) {
			case "GeometryCollection":
				o.geometries.forEach(bboxGeometry);
				break;
			case "Point":
				bboxPoint(o.coordinates);
				break;
			case "MultiPoint":
				o.coordinates.forEach(bboxPoint);
				break;
		}
	}
	topology.arcs.forEach(function(arc) {
		var i = -1, n = arc.length, p;
		while (++i < n) {
			p = t(arc[i], i);
			if (p[0] < x0) x0 = p[0];
			if (p[0] > x1) x1 = p[0];
			if (p[1] < y0) y0 = p[1];
			if (p[1] > y1) y1 = p[1];
		}
	});
	for (key in topology.objects) bboxGeometry(topology.objects[key]);
	return [
		x0,
		y0,
		x1,
		y1
	];
}
var init_bbox = __esmMin((() => {
	init_transform();
}));
//#endregion
//#region node_modules/topojson-client/src/reverse.js
function reverse_default(array, n) {
	var t, j = array.length, i = j - n;
	while (i < --j) t = array[i], array[i++] = array[j], array[j] = t;
}
var init_reverse = __esmMin((() => {}));
//#endregion
//#region node_modules/topojson-client/src/feature.js
function feature_default(topology, o) {
	if (typeof o === "string") o = topology.objects[o];
	return o.type === "GeometryCollection" ? {
		type: "FeatureCollection",
		features: o.geometries.map(function(o) {
			return feature(topology, o);
		})
	} : feature(topology, o);
}
function feature(topology, o) {
	var id = o.id, bbox = o.bbox, properties = o.properties == null ? {} : o.properties, geometry = object(topology, o);
	return id == null && bbox == null ? {
		type: "Feature",
		properties,
		geometry
	} : bbox == null ? {
		type: "Feature",
		id,
		properties,
		geometry
	} : {
		type: "Feature",
		id,
		bbox,
		properties,
		geometry
	};
}
function object(topology, o) {
	var transformPoint = transform_default(topology.transform), arcs = topology.arcs;
	function arc(i, points) {
		if (points.length) points.pop();
		for (var a = arcs[i < 0 ? ~i : i], k = 0, n = a.length; k < n; ++k) points.push(transformPoint(a[k], k));
		if (i < 0) reverse_default(points, n);
	}
	function point(p) {
		return transformPoint(p);
	}
	function line(arcs) {
		var points = [];
		for (var i = 0, n = arcs.length; i < n; ++i) arc(arcs[i], points);
		if (points.length < 2) points.push(points[0]);
		return points;
	}
	function ring(arcs) {
		var points = line(arcs);
		while (points.length < 4) points.push(points[0]);
		return points;
	}
	function polygon(arcs) {
		return arcs.map(ring);
	}
	function geometry(o) {
		var type = o.type, coordinates;
		switch (type) {
			case "GeometryCollection": return {
				type,
				geometries: o.geometries.map(geometry)
			};
			case "Point":
				coordinates = point(o.coordinates);
				break;
			case "MultiPoint":
				coordinates = o.coordinates.map(point);
				break;
			case "LineString":
				coordinates = line(o.arcs);
				break;
			case "MultiLineString":
				coordinates = o.arcs.map(line);
				break;
			case "Polygon":
				coordinates = polygon(o.arcs);
				break;
			case "MultiPolygon":
				coordinates = o.arcs.map(polygon);
				break;
			default: return null;
		}
		return {
			type,
			coordinates
		};
	}
	return geometry(o);
}
var init_feature = __esmMin((() => {
	init_reverse();
	init_transform();
}));
//#endregion
//#region node_modules/topojson-client/src/stitch.js
function stitch_default(topology, arcs) {
	var stitchedArcs = {}, fragmentByStart = {}, fragmentByEnd = {}, fragments = [], emptyIndex = -1;
	arcs.forEach(function(i, j) {
		var arc = topology.arcs[i < 0 ? ~i : i], t;
		if (arc.length < 3 && !arc[1][0] && !arc[1][1]) t = arcs[++emptyIndex], arcs[emptyIndex] = i, arcs[j] = t;
	});
	arcs.forEach(function(i) {
		var e = ends(i), start = e[0], end = e[1], f, g;
		if (f = fragmentByEnd[start]) {
			delete fragmentByEnd[f.end];
			f.push(i);
			f.end = end;
			if (g = fragmentByStart[end]) {
				delete fragmentByStart[g.start];
				var fg = g === f ? f : f.concat(g);
				fragmentByStart[fg.start = f.start] = fragmentByEnd[fg.end = g.end] = fg;
			} else fragmentByStart[f.start] = fragmentByEnd[f.end] = f;
		} else if (f = fragmentByStart[end]) {
			delete fragmentByStart[f.start];
			f.unshift(i);
			f.start = start;
			if (g = fragmentByEnd[start]) {
				delete fragmentByEnd[g.end];
				var gf = g === f ? f : g.concat(f);
				fragmentByStart[gf.start = g.start] = fragmentByEnd[gf.end = f.end] = gf;
			} else fragmentByStart[f.start] = fragmentByEnd[f.end] = f;
		} else {
			f = [i];
			fragmentByStart[f.start = start] = fragmentByEnd[f.end = end] = f;
		}
	});
	function ends(i) {
		var arc = topology.arcs[i < 0 ? ~i : i], p0 = arc[0], p1;
		if (topology.transform) p1 = [0, 0], arc.forEach(function(dp) {
			p1[0] += dp[0], p1[1] += dp[1];
		});
		else p1 = arc[arc.length - 1];
		return i < 0 ? [p1, p0] : [p0, p1];
	}
	function flush(fragmentByEnd, fragmentByStart) {
		for (var k in fragmentByEnd) {
			var f = fragmentByEnd[k];
			delete fragmentByStart[f.start];
			delete f.start;
			delete f.end;
			f.forEach(function(i) {
				stitchedArcs[i < 0 ? ~i : i] = 1;
			});
			fragments.push(f);
		}
	}
	flush(fragmentByEnd, fragmentByStart);
	flush(fragmentByStart, fragmentByEnd);
	arcs.forEach(function(i) {
		if (!stitchedArcs[i < 0 ? ~i : i]) fragments.push([i]);
	});
	return fragments;
}
var init_stitch = __esmMin((() => {}));
//#endregion
//#region node_modules/topojson-client/src/mesh.js
function mesh_default(topology) {
	return object(topology, meshArcs.apply(this, arguments));
}
function meshArcs(topology, object, filter) {
	var arcs, i, n;
	if (arguments.length > 1) arcs = extractArcs(topology, object, filter);
	else for (i = 0, arcs = new Array(n = topology.arcs.length); i < n; ++i) arcs[i] = i;
	return {
		type: "MultiLineString",
		arcs: stitch_default(topology, arcs)
	};
}
function extractArcs(topology, object, filter) {
	var arcs = [], geomsByArc = [], geom;
	function extract0(i) {
		var j = i < 0 ? ~i : i;
		(geomsByArc[j] || (geomsByArc[j] = [])).push({
			i,
			g: geom
		});
	}
	function extract1(arcs) {
		arcs.forEach(extract0);
	}
	function extract2(arcs) {
		arcs.forEach(extract1);
	}
	function extract3(arcs) {
		arcs.forEach(extract2);
	}
	function geometry(o) {
		switch (geom = o, o.type) {
			case "GeometryCollection":
				o.geometries.forEach(geometry);
				break;
			case "LineString":
				extract1(o.arcs);
				break;
			case "MultiLineString":
			case "Polygon":
				extract2(o.arcs);
				break;
			case "MultiPolygon":
				extract3(o.arcs);
				break;
		}
	}
	geometry(object);
	geomsByArc.forEach(filter == null ? function(geoms) {
		arcs.push(geoms[0].i);
	} : function(geoms) {
		if (filter(geoms[0].g, geoms[geoms.length - 1].g)) arcs.push(geoms[0].i);
	});
	return arcs;
}
var init_mesh = __esmMin((() => {
	init_feature();
	init_stitch();
}));
//#endregion
//#region node_modules/topojson-client/src/merge.js
function planarRingArea(ring) {
	var i = -1, n = ring.length, a, b = ring[n - 1], area = 0;
	while (++i < n) a = b, b = ring[i], area += a[0] * b[1] - a[1] * b[0];
	return Math.abs(area);
}
function merge_default(topology) {
	return object(topology, mergeArcs.apply(this, arguments));
}
function mergeArcs(topology, objects) {
	var polygonsByArc = {}, polygons = [], groups = [];
	objects.forEach(geometry);
	function geometry(o) {
		switch (o.type) {
			case "GeometryCollection":
				o.geometries.forEach(geometry);
				break;
			case "Polygon":
				extract(o.arcs);
				break;
			case "MultiPolygon":
				o.arcs.forEach(extract);
				break;
		}
	}
	function extract(polygon) {
		polygon.forEach(function(ring) {
			ring.forEach(function(arc) {
				(polygonsByArc[arc = arc < 0 ? ~arc : arc] || (polygonsByArc[arc] = [])).push(polygon);
			});
		});
		polygons.push(polygon);
	}
	function area(ring) {
		return planarRingArea(object(topology, {
			type: "Polygon",
			arcs: [ring]
		}).coordinates[0]);
	}
	polygons.forEach(function(polygon) {
		if (!polygon._) {
			var group = [], neighbors = [polygon];
			polygon._ = 1;
			groups.push(group);
			while (polygon = neighbors.pop()) {
				group.push(polygon);
				polygon.forEach(function(ring) {
					ring.forEach(function(arc) {
						polygonsByArc[arc < 0 ? ~arc : arc].forEach(function(polygon) {
							if (!polygon._) {
								polygon._ = 1;
								neighbors.push(polygon);
							}
						});
					});
				});
			}
		}
	});
	polygons.forEach(function(polygon) {
		delete polygon._;
	});
	return {
		type: "MultiPolygon",
		arcs: groups.map(function(polygons) {
			var arcs = [], n;
			polygons.forEach(function(polygon) {
				polygon.forEach(function(ring) {
					ring.forEach(function(arc) {
						if (polygonsByArc[arc < 0 ? ~arc : arc].length < 2) arcs.push(arc);
					});
				});
			});
			arcs = stitch_default(topology, arcs);
			if ((n = arcs.length) > 1) {
				for (var i = 1, k = area(arcs[0]), ki, t; i < n; ++i) if ((ki = area(arcs[i])) > k) t = arcs[0], arcs[0] = arcs[i], arcs[i] = t, k = ki;
			}
			return arcs;
		}).filter(function(arcs) {
			return arcs.length > 0;
		})
	};
}
var init_merge = __esmMin((() => {
	init_feature();
	init_stitch();
}));
//#endregion
//#region node_modules/topojson-client/src/bisect.js
function bisect_default(a, x) {
	var lo = 0, hi = a.length;
	while (lo < hi) {
		var mid = lo + hi >>> 1;
		if (a[mid] < x) lo = mid + 1;
		else hi = mid;
	}
	return lo;
}
var init_bisect = __esmMin((() => {}));
//#endregion
//#region node_modules/topojson-client/src/neighbors.js
function neighbors_default(objects) {
	var indexesByArc = {}, neighbors = objects.map(function() {
		return [];
	});
	function line(arcs, i) {
		arcs.forEach(function(a) {
			if (a < 0) a = ~a;
			var o = indexesByArc[a];
			if (o) o.push(i);
			else indexesByArc[a] = [i];
		});
	}
	function polygon(arcs, i) {
		arcs.forEach(function(arc) {
			line(arc, i);
		});
	}
	function geometry(o, i) {
		if (o.type === "GeometryCollection") o.geometries.forEach(function(o) {
			geometry(o, i);
		});
		else if (o.type in geometryType) geometryType[o.type](o.arcs, i);
	}
	var geometryType = {
		LineString: line,
		MultiLineString: polygon,
		Polygon: polygon,
		MultiPolygon: function(arcs, i) {
			arcs.forEach(function(arc) {
				polygon(arc, i);
			});
		}
	};
	objects.forEach(geometry);
	for (var i in indexesByArc) for (var indexes = indexesByArc[i], m = indexes.length, j = 0; j < m; ++j) for (var k = j + 1; k < m; ++k) {
		var ij = indexes[j], ik = indexes[k], n;
		if ((n = neighbors[ij])[i = bisect_default(n, ik)] !== ik) n.splice(i, 0, ik);
		if ((n = neighbors[ik])[i = bisect_default(n, ij)] !== ij) n.splice(i, 0, ij);
	}
	return neighbors;
}
var init_neighbors = __esmMin((() => {
	init_bisect();
}));
//#endregion
//#region node_modules/topojson-client/src/untransform.js
function untransform_default(transform) {
	if (transform == null) return identity_default;
	var x0, y0, kx = transform.scale[0], ky = transform.scale[1], dx = transform.translate[0], dy = transform.translate[1];
	return function(input, i) {
		if (!i) x0 = y0 = 0;
		var j = 2, n = input.length, output = new Array(n), x1 = Math.round((input[0] - dx) / kx), y1 = Math.round((input[1] - dy) / ky);
		output[0] = x1 - x0, x0 = x1;
		output[1] = y1 - y0, y0 = y1;
		while (j < n) output[j] = input[j], ++j;
		return output;
	};
}
var init_untransform = __esmMin((() => {
	init_identity();
}));
//#endregion
//#region node_modules/topojson-client/src/quantize.js
function quantize_default(topology, transform) {
	if (topology.transform) throw new Error("already quantized");
	if (!transform || !transform.scale) {
		if (!((n = Math.floor(transform)) >= 2)) throw new Error("n must be ≥2");
		box = topology.bbox || bbox_default(topology);
		var x0 = box[0], y0 = box[1], x1 = box[2], y1 = box[3], n;
		transform = {
			scale: [x1 - x0 ? (x1 - x0) / (n - 1) : 1, y1 - y0 ? (y1 - y0) / (n - 1) : 1],
			translate: [x0, y0]
		};
	} else box = topology.bbox;
	var t = untransform_default(transform), box, key, inputs = topology.objects, outputs = {};
	function quantizePoint(point) {
		return t(point);
	}
	function quantizeGeometry(input) {
		var output;
		switch (input.type) {
			case "GeometryCollection":
				output = {
					type: "GeometryCollection",
					geometries: input.geometries.map(quantizeGeometry)
				};
				break;
			case "Point":
				output = {
					type: "Point",
					coordinates: quantizePoint(input.coordinates)
				};
				break;
			case "MultiPoint":
				output = {
					type: "MultiPoint",
					coordinates: input.coordinates.map(quantizePoint)
				};
				break;
			default: return input;
		}
		if (input.id != null) output.id = input.id;
		if (input.bbox != null) output.bbox = input.bbox;
		if (input.properties != null) output.properties = input.properties;
		return output;
	}
	function quantizeArc(input) {
		var i = 0, j = 1, n = input.length, p, output = new Array(n);
		output[0] = t(input[0], 0);
		while (++i < n) if ((p = t(input[i], i))[0] || p[1]) output[j++] = p;
		if (j === 1) output[j++] = [0, 0];
		output.length = j;
		return output;
	}
	for (key in inputs) outputs[key] = quantizeGeometry(inputs[key]);
	return {
		type: "Topology",
		bbox: box,
		transform,
		objects: outputs,
		arcs: topology.arcs.map(quantizeArc)
	};
}
var init_quantize = __esmMin((() => {
	init_bbox();
	init_untransform();
}));
//#endregion
//#region node_modules/topojson-client/src/index.js
var src_exports = /* @__PURE__ */ __exportAll({
	bbox: () => bbox_default,
	feature: () => feature_default,
	merge: () => merge_default,
	mergeArcs: () => mergeArcs,
	mesh: () => mesh_default,
	meshArcs: () => meshArcs,
	neighbors: () => neighbors_default,
	quantize: () => quantize_default,
	transform: () => transform_default,
	untransform: () => untransform_default
});
var init_src = __esmMin((() => {
	init_bbox();
	init_feature();
	init_mesh();
	init_merge();
	init_neighbors();
	init_quantize();
	init_transform();
	init_untransform();
}));
//#endregion
export { bbox_default as _, init_untransform as a, transform_default as b, neighbors_default as c, merge_default as d, init_mesh as f, init_feature as g, feature_default as h, quantize_default as i, init_merge as l, mesh_default as m, src_exports as n, untransform_default as o, meshArcs as p, init_quantize as r, init_neighbors as s, init_src as t, mergeArcs as u, init_bbox as v, init_transform as y };

//# sourceMappingURL=src--fPnIpbL.js.map