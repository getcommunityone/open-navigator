import { i as __toCommonJS, n as __esmMin, r as __exportAll, t as __commonJSMin } from "./chunk-_TIqcEvS.js";
import { t as require_react } from "./react.js";
import { t as require_prop_types } from "./prop-types-WOmwsC-r.js";
import { n as src_exports$2, t as init_src$3 } from "./src--fPnIpbL.js";
import { n as src_exports$3, t as init_src$4 } from "./src-CvDk-rGq.js";
//#region node_modules/react-simple-maps/node_modules/d3-array/src/fsum.js
var Adder;
var init_fsum = __esmMin((() => {
	Adder = class {
		constructor() {
			this._partials = new Float64Array(32);
			this._n = 0;
		}
		add(x) {
			const p = this._partials;
			let i = 0;
			for (let j = 0; j < this._n && j < 32; j++) {
				const y = p[j], hi = x + y, lo = Math.abs(x) < Math.abs(y) ? x - (hi - y) : y - (hi - x);
				if (lo) p[i++] = lo;
				x = hi;
			}
			p[i] = x;
			this._n = i + 1;
			return this;
		}
		valueOf() {
			const p = this._partials;
			let n = this._n, x, y, lo, hi = 0;
			if (n > 0) {
				hi = p[--n];
				while (n > 0) {
					x = hi;
					y = p[--n];
					hi = x + y;
					lo = y - (hi - x);
					if (lo) break;
				}
				if (n > 0 && (lo < 0 && p[n - 1] < 0 || lo > 0 && p[n - 1] > 0)) {
					y = lo * 2;
					x = hi + y;
					if (y == x - hi) hi = x;
				}
			}
			return hi;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-array/src/merge.js
function* flatten(arrays) {
	for (const array of arrays) yield* array;
}
function merge(arrays) {
	return Array.from(flatten(arrays));
}
var init_merge$1 = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-array/src/range.js
function range_default(start, stop, step) {
	start = +start, stop = +stop, step = (n = arguments.length) < 2 ? (stop = start, start = 0, 1) : n < 3 ? 1 : +step;
	var i = -1, n = Math.max(0, Math.ceil((stop - start) / step)) | 0, range = new Array(n);
	while (++i < n) range[i] = start + i * step;
	return range;
}
var init_range = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-array/src/index.js
var init_src$2 = __esmMin((() => {
	init_fsum();
	init_merge$1();
	init_range();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/math.js
function acos(x) {
	return x > 1 ? 0 : x < -1 ? pi : Math.acos(x);
}
function asin(x) {
	return x > 1 ? halfPi : x < -1 ? -halfPi : Math.asin(x);
}
function haversin(x) {
	return (x = sin(x / 2)) * x;
}
var epsilon, pi, halfPi, quarterPi, tau, degrees, radians, abs, atan, atan2, cos, ceil, exp, hypot, log, pow, sin, sign, sqrt, tan;
var init_math = __esmMin((() => {
	epsilon = 1e-6;
	pi = Math.PI;
	halfPi = pi / 2;
	quarterPi = pi / 4;
	tau = pi * 2;
	degrees = 180 / pi;
	radians = pi / 180;
	abs = Math.abs;
	atan = Math.atan;
	atan2 = Math.atan2;
	cos = Math.cos;
	ceil = Math.ceil;
	exp = Math.exp;
	hypot = Math.hypot;
	log = Math.log;
	pow = Math.pow;
	sin = Math.sin;
	sign = Math.sign || function(x) {
		return x > 0 ? 1 : x < 0 ? -1 : 0;
	};
	sqrt = Math.sqrt;
	tan = Math.tan;
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/noop.js
function noop() {}
var init_noop = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/stream.js
function streamGeometry(geometry, stream) {
	if (geometry && streamGeometryType.hasOwnProperty(geometry.type)) streamGeometryType[geometry.type](geometry, stream);
}
function streamLine(coordinates, stream, closed) {
	var i = -1, n = coordinates.length - closed, coordinate;
	stream.lineStart();
	while (++i < n) coordinate = coordinates[i], stream.point(coordinate[0], coordinate[1], coordinate[2]);
	stream.lineEnd();
}
function streamPolygon(coordinates, stream) {
	var i = -1, n = coordinates.length;
	stream.polygonStart();
	while (++i < n) streamLine(coordinates[i], stream, 1);
	stream.polygonEnd();
}
function stream_default(object, stream) {
	if (object && streamObjectType.hasOwnProperty(object.type)) streamObjectType[object.type](object, stream);
	else streamGeometry(object, stream);
}
var streamObjectType, streamGeometryType;
var init_stream = __esmMin((() => {
	streamObjectType = {
		Feature: function(object, stream) {
			streamGeometry(object.geometry, stream);
		},
		FeatureCollection: function(object, stream) {
			var features = object.features, i = -1, n = features.length;
			while (++i < n) streamGeometry(features[i].geometry, stream);
		}
	};
	streamGeometryType = {
		Sphere: function(object, stream) {
			stream.sphere();
		},
		Point: function(object, stream) {
			object = object.coordinates;
			stream.point(object[0], object[1], object[2]);
		},
		MultiPoint: function(object, stream) {
			var coordinates = object.coordinates, i = -1, n = coordinates.length;
			while (++i < n) object = coordinates[i], stream.point(object[0], object[1], object[2]);
		},
		LineString: function(object, stream) {
			streamLine(object.coordinates, stream, 0);
		},
		MultiLineString: function(object, stream) {
			var coordinates = object.coordinates, i = -1, n = coordinates.length;
			while (++i < n) streamLine(coordinates[i], stream, 0);
		},
		Polygon: function(object, stream) {
			streamPolygon(object.coordinates, stream);
		},
		MultiPolygon: function(object, stream) {
			var coordinates = object.coordinates, i = -1, n = coordinates.length;
			while (++i < n) streamPolygon(coordinates[i], stream);
		},
		GeometryCollection: function(object, stream) {
			var geometries = object.geometries, i = -1, n = geometries.length;
			while (++i < n) streamGeometry(geometries[i], stream);
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/area.js
function areaRingStart$1() {
	areaStream$1.point = areaPointFirst$1;
}
function areaRingEnd$1() {
	areaPoint$1(lambda00$2, phi00$2);
}
function areaPointFirst$1(lambda, phi) {
	areaStream$1.point = areaPoint$1;
	lambda00$2 = lambda, phi00$2 = phi;
	lambda *= radians, phi *= radians;
	lambda0$2 = lambda, cosPhi0$1 = cos(phi = phi / 2 + quarterPi), sinPhi0$1 = sin(phi);
}
function areaPoint$1(lambda, phi) {
	lambda *= radians, phi *= radians;
	phi = phi / 2 + quarterPi;
	var dLambda = lambda - lambda0$2, sdLambda = dLambda >= 0 ? 1 : -1, adLambda = sdLambda * dLambda, cosPhi = cos(phi), sinPhi = sin(phi), k = sinPhi0$1 * sinPhi, u = cosPhi0$1 * cosPhi + k * cos(adLambda), v = k * sdLambda * sin(adLambda);
	areaRingSum$1.add(atan2(v, u));
	lambda0$2 = lambda, cosPhi0$1 = cosPhi, sinPhi0$1 = sinPhi;
}
function area_default(object) {
	areaSum$1 = new Adder();
	stream_default(object, areaStream$1);
	return areaSum$1 * 2;
}
var areaRingSum$1, areaSum$1, lambda00$2, phi00$2, lambda0$2, cosPhi0$1, sinPhi0$1, areaStream$1;
var init_area$1 = __esmMin((() => {
	init_src$2();
	init_math();
	init_noop();
	init_stream();
	areaRingSum$1 = new Adder();
	areaSum$1 = new Adder();
	areaStream$1 = {
		point: noop,
		lineStart: noop,
		lineEnd: noop,
		polygonStart: function() {
			areaRingSum$1 = new Adder();
			areaStream$1.lineStart = areaRingStart$1;
			areaStream$1.lineEnd = areaRingEnd$1;
		},
		polygonEnd: function() {
			var areaRing = +areaRingSum$1;
			areaSum$1.add(areaRing < 0 ? tau + areaRing : areaRing);
			this.lineStart = this.lineEnd = this.point = noop;
		},
		sphere: function() {
			areaSum$1.add(tau);
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/cartesian.js
function spherical(cartesian) {
	return [atan2(cartesian[1], cartesian[0]), asin(cartesian[2])];
}
function cartesian(spherical) {
	var lambda = spherical[0], phi = spherical[1], cosPhi = cos(phi);
	return [
		cosPhi * cos(lambda),
		cosPhi * sin(lambda),
		sin(phi)
	];
}
function cartesianDot(a, b) {
	return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
function cartesianCross(a, b) {
	return [
		a[1] * b[2] - a[2] * b[1],
		a[2] * b[0] - a[0] * b[2],
		a[0] * b[1] - a[1] * b[0]
	];
}
function cartesianAddInPlace(a, b) {
	a[0] += b[0], a[1] += b[1], a[2] += b[2];
}
function cartesianScale(vector, k) {
	return [
		vector[0] * k,
		vector[1] * k,
		vector[2] * k
	];
}
function cartesianNormalizeInPlace(d) {
	var l = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
	d[0] /= l, d[1] /= l, d[2] /= l;
}
var init_cartesian = __esmMin((() => {
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/bounds.js
function boundsPoint$1(lambda, phi) {
	ranges.push(range = [lambda0$1 = lambda, lambda1 = lambda]);
	if (phi < phi0) phi0 = phi;
	if (phi > phi1) phi1 = phi;
}
function linePoint(lambda, phi) {
	var p = cartesian([lambda * radians, phi * radians]);
	if (p0) {
		var normal = cartesianCross(p0, p), inflection = cartesianCross([
			normal[1],
			-normal[0],
			0
		], normal);
		cartesianNormalizeInPlace(inflection);
		inflection = spherical(inflection);
		var delta = lambda - lambda2, sign = delta > 0 ? 1 : -1, lambdai = inflection[0] * degrees * sign, phii, antimeridian = abs(delta) > 180;
		if (antimeridian ^ (sign * lambda2 < lambdai && lambdai < sign * lambda)) {
			phii = inflection[1] * degrees;
			if (phii > phi1) phi1 = phii;
		} else if (lambdai = (lambdai + 360) % 360 - 180, antimeridian ^ (sign * lambda2 < lambdai && lambdai < sign * lambda)) {
			phii = -inflection[1] * degrees;
			if (phii < phi0) phi0 = phii;
		} else {
			if (phi < phi0) phi0 = phi;
			if (phi > phi1) phi1 = phi;
		}
		if (antimeridian) {
			if (lambda < lambda2) {
				if (angle(lambda0$1, lambda) > angle(lambda0$1, lambda1)) lambda1 = lambda;
			} else if (angle(lambda, lambda1) > angle(lambda0$1, lambda1)) lambda0$1 = lambda;
		} else if (lambda1 >= lambda0$1) {
			if (lambda < lambda0$1) lambda0$1 = lambda;
			if (lambda > lambda1) lambda1 = lambda;
		} else if (lambda > lambda2) {
			if (angle(lambda0$1, lambda) > angle(lambda0$1, lambda1)) lambda1 = lambda;
		} else if (angle(lambda, lambda1) > angle(lambda0$1, lambda1)) lambda0$1 = lambda;
	} else ranges.push(range = [lambda0$1 = lambda, lambda1 = lambda]);
	if (phi < phi0) phi0 = phi;
	if (phi > phi1) phi1 = phi;
	p0 = p, lambda2 = lambda;
}
function boundsLineStart() {
	boundsStream$1.point = linePoint;
}
function boundsLineEnd() {
	range[0] = lambda0$1, range[1] = lambda1;
	boundsStream$1.point = boundsPoint$1;
	p0 = null;
}
function boundsRingPoint(lambda, phi) {
	if (p0) {
		var delta = lambda - lambda2;
		deltaSum.add(abs(delta) > 180 ? delta + (delta > 0 ? 360 : -360) : delta);
	} else lambda00$1 = lambda, phi00$1 = phi;
	areaStream$1.point(lambda, phi);
	linePoint(lambda, phi);
}
function boundsRingStart() {
	areaStream$1.lineStart();
}
function boundsRingEnd() {
	boundsRingPoint(lambda00$1, phi00$1);
	areaStream$1.lineEnd();
	if (abs(deltaSum) > 1e-6) lambda0$1 = -(lambda1 = 180);
	range[0] = lambda0$1, range[1] = lambda1;
	p0 = null;
}
function angle(lambda0, lambda1) {
	return (lambda1 -= lambda0) < 0 ? lambda1 + 360 : lambda1;
}
function rangeCompare(a, b) {
	return a[0] - b[0];
}
function rangeContains(range, x) {
	return range[0] <= range[1] ? range[0] <= x && x <= range[1] : x < range[0] || range[1] < x;
}
function bounds_default(feature) {
	var i, n, a, b, merged, deltaMax, delta;
	phi1 = lambda1 = -(lambda0$1 = phi0 = Infinity);
	ranges = [];
	stream_default(feature, boundsStream$1);
	if (n = ranges.length) {
		ranges.sort(rangeCompare);
		for (i = 1, a = ranges[0], merged = [a]; i < n; ++i) {
			b = ranges[i];
			if (rangeContains(a, b[0]) || rangeContains(a, b[1])) {
				if (angle(a[0], b[1]) > angle(a[0], a[1])) a[1] = b[1];
				if (angle(b[0], a[1]) > angle(a[0], a[1])) a[0] = b[0];
			} else merged.push(a = b);
		}
		for (deltaMax = -Infinity, n = merged.length - 1, i = 0, a = merged[n]; i <= n; a = b, ++i) {
			b = merged[i];
			if ((delta = angle(a[1], b[0])) > deltaMax) deltaMax = delta, lambda0$1 = b[0], lambda1 = a[1];
		}
	}
	ranges = range = null;
	return lambda0$1 === Infinity || phi0 === Infinity ? [[NaN, NaN], [NaN, NaN]] : [[lambda0$1, phi0], [lambda1, phi1]];
}
var lambda0$1, phi0, lambda1, phi1, lambda2, lambda00$1, phi00$1, p0, deltaSum, ranges, range, boundsStream$1;
var init_bounds$1 = __esmMin((() => {
	init_src$2();
	init_area$1();
	init_cartesian();
	init_math();
	init_stream();
	boundsStream$1 = {
		point: boundsPoint$1,
		lineStart: boundsLineStart,
		lineEnd: boundsLineEnd,
		polygonStart: function() {
			boundsStream$1.point = boundsRingPoint;
			boundsStream$1.lineStart = boundsRingStart;
			boundsStream$1.lineEnd = boundsRingEnd;
			deltaSum = new Adder();
			areaStream$1.polygonStart();
		},
		polygonEnd: function() {
			areaStream$1.polygonEnd();
			boundsStream$1.point = boundsPoint$1;
			boundsStream$1.lineStart = boundsLineStart;
			boundsStream$1.lineEnd = boundsLineEnd;
			if (areaRingSum$1 < 0) lambda0$1 = -(lambda1 = 180), phi0 = -(phi1 = 90);
			else if (deltaSum > 1e-6) phi1 = 90;
			else if (deltaSum < -1e-6) phi0 = -90;
			range[0] = lambda0$1, range[1] = lambda1;
		},
		sphere: function() {
			lambda0$1 = -(lambda1 = 180), phi0 = -(phi1 = 90);
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/centroid.js
function centroidPoint$1(lambda, phi) {
	lambda *= radians, phi *= radians;
	var cosPhi = cos(phi);
	centroidPointCartesian(cosPhi * cos(lambda), cosPhi * sin(lambda), sin(phi));
}
function centroidPointCartesian(x, y, z) {
	++W0;
	X0$1 += (x - X0$1) / W0;
	Y0$1 += (y - Y0$1) / W0;
	Z0$1 += (z - Z0$1) / W0;
}
function centroidLineStart$1() {
	centroidStream$1.point = centroidLinePointFirst;
}
function centroidLinePointFirst(lambda, phi) {
	lambda *= radians, phi *= radians;
	var cosPhi = cos(phi);
	x0$4 = cosPhi * cos(lambda);
	y0$4 = cosPhi * sin(lambda);
	z0 = sin(phi);
	centroidStream$1.point = centroidLinePoint;
	centroidPointCartesian(x0$4, y0$4, z0);
}
function centroidLinePoint(lambda, phi) {
	lambda *= radians, phi *= radians;
	var cosPhi = cos(phi), x = cosPhi * cos(lambda), y = cosPhi * sin(lambda), z = sin(phi), w = atan2(sqrt((w = y0$4 * z - z0 * y) * w + (w = z0 * x - x0$4 * z) * w + (w = x0$4 * y - y0$4 * x) * w), x0$4 * x + y0$4 * y + z0 * z);
	W1 += w;
	X1$1 += w * (x0$4 + (x0$4 = x));
	Y1$1 += w * (y0$4 + (y0$4 = y));
	Z1$1 += w * (z0 + (z0 = z));
	centroidPointCartesian(x0$4, y0$4, z0);
}
function centroidLineEnd$1() {
	centroidStream$1.point = centroidPoint$1;
}
function centroidRingStart$1() {
	centroidStream$1.point = centroidRingPointFirst;
}
function centroidRingEnd$1() {
	centroidRingPoint(lambda00, phi00);
	centroidStream$1.point = centroidPoint$1;
}
function centroidRingPointFirst(lambda, phi) {
	lambda00 = lambda, phi00 = phi;
	lambda *= radians, phi *= radians;
	centroidStream$1.point = centroidRingPoint;
	var cosPhi = cos(phi);
	x0$4 = cosPhi * cos(lambda);
	y0$4 = cosPhi * sin(lambda);
	z0 = sin(phi);
	centroidPointCartesian(x0$4, y0$4, z0);
}
function centroidRingPoint(lambda, phi) {
	lambda *= radians, phi *= radians;
	var cosPhi = cos(phi), x = cosPhi * cos(lambda), y = cosPhi * sin(lambda), z = sin(phi), cx = y0$4 * z - z0 * y, cy = z0 * x - x0$4 * z, cz = x0$4 * y - y0$4 * x, m = hypot(cx, cy, cz), w = asin(m), v = m && -w / m;
	X2$1.add(v * cx);
	Y2$1.add(v * cy);
	Z2$1.add(v * cz);
	W1 += w;
	X1$1 += w * (x0$4 + (x0$4 = x));
	Y1$1 += w * (y0$4 + (y0$4 = y));
	Z1$1 += w * (z0 + (z0 = z));
	centroidPointCartesian(x0$4, y0$4, z0);
}
function centroid_default(object) {
	W0 = W1 = X0$1 = Y0$1 = Z0$1 = X1$1 = Y1$1 = Z1$1 = 0;
	X2$1 = new Adder();
	Y2$1 = new Adder();
	Z2$1 = new Adder();
	stream_default(object, centroidStream$1);
	var x = +X2$1, y = +Y2$1, z = +Z2$1, m = hypot(x, y, z);
	if (m < 1e-12) {
		x = X1$1, y = Y1$1, z = Z1$1;
		if (W1 < 1e-6) x = X0$1, y = Y0$1, z = Z0$1;
		m = hypot(x, y, z);
		if (m < 1e-12) return [NaN, NaN];
	}
	return [atan2(y, x) * degrees, asin(z / m) * degrees];
}
var W0, W1, X0$1, Y0$1, Z0$1, X1$1, Y1$1, Z1$1, X2$1, Y2$1, Z2$1, lambda00, phi00, x0$4, y0$4, z0, centroidStream$1;
var init_centroid$1 = __esmMin((() => {
	init_src$2();
	init_math();
	init_noop();
	init_stream();
	centroidStream$1 = {
		sphere: noop,
		point: centroidPoint$1,
		lineStart: centroidLineStart$1,
		lineEnd: centroidLineEnd$1,
		polygonStart: function() {
			centroidStream$1.lineStart = centroidRingStart$1;
			centroidStream$1.lineEnd = centroidRingEnd$1;
		},
		polygonEnd: function() {
			centroidStream$1.lineStart = centroidLineStart$1;
			centroidStream$1.lineEnd = centroidLineEnd$1;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/constant.js
function constant_default$1(x) {
	return function() {
		return x;
	};
}
var init_constant$1 = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/compose.js
function compose_default(a, b) {
	function compose(x, y) {
		return x = a(x, y), b(x[0], x[1]);
	}
	if (a.invert && b.invert) compose.invert = function(x, y) {
		return x = b.invert(x, y), x && a.invert(x[0], x[1]);
	};
	return compose;
}
var init_compose = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/rotation.js
function rotationIdentity(lambda, phi) {
	return [abs(lambda) > pi ? lambda + Math.round(-lambda / tau) * tau : lambda, phi];
}
function rotateRadians(deltaLambda, deltaPhi, deltaGamma) {
	return (deltaLambda %= tau) ? deltaPhi || deltaGamma ? compose_default(rotationLambda(deltaLambda), rotationPhiGamma(deltaPhi, deltaGamma)) : rotationLambda(deltaLambda) : deltaPhi || deltaGamma ? rotationPhiGamma(deltaPhi, deltaGamma) : rotationIdentity;
}
function forwardRotationLambda(deltaLambda) {
	return function(lambda, phi) {
		return lambda += deltaLambda, [lambda > pi ? lambda - tau : lambda < -pi ? lambda + tau : lambda, phi];
	};
}
function rotationLambda(deltaLambda) {
	var rotation = forwardRotationLambda(deltaLambda);
	rotation.invert = forwardRotationLambda(-deltaLambda);
	return rotation;
}
function rotationPhiGamma(deltaPhi, deltaGamma) {
	var cosDeltaPhi = cos(deltaPhi), sinDeltaPhi = sin(deltaPhi), cosDeltaGamma = cos(deltaGamma), sinDeltaGamma = sin(deltaGamma);
	function rotation(lambda, phi) {
		var cosPhi = cos(phi), x = cos(lambda) * cosPhi, y = sin(lambda) * cosPhi, z = sin(phi), k = z * cosDeltaPhi + x * sinDeltaPhi;
		return [atan2(y * cosDeltaGamma - k * sinDeltaGamma, x * cosDeltaPhi - z * sinDeltaPhi), asin(k * cosDeltaGamma + y * sinDeltaGamma)];
	}
	rotation.invert = function(lambda, phi) {
		var cosPhi = cos(phi), x = cos(lambda) * cosPhi, y = sin(lambda) * cosPhi, z = sin(phi), k = z * cosDeltaGamma - y * sinDeltaGamma;
		return [atan2(y * cosDeltaGamma + z * sinDeltaGamma, x * cosDeltaPhi + k * sinDeltaPhi), asin(k * cosDeltaPhi - x * sinDeltaPhi)];
	};
	return rotation;
}
function rotation_default(rotate) {
	rotate = rotateRadians(rotate[0] * radians, rotate[1] * radians, rotate.length > 2 ? rotate[2] * radians : 0);
	function forward(coordinates) {
		coordinates = rotate(coordinates[0] * radians, coordinates[1] * radians);
		return coordinates[0] *= degrees, coordinates[1] *= degrees, coordinates;
	}
	forward.invert = function(coordinates) {
		coordinates = rotate.invert(coordinates[0] * radians, coordinates[1] * radians);
		return coordinates[0] *= degrees, coordinates[1] *= degrees, coordinates;
	};
	return forward;
}
var init_rotation = __esmMin((() => {
	init_compose();
	init_math();
	rotationIdentity.invert = rotationIdentity;
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/circle.js
function circleStream(stream, radius, delta, direction, t0, t1) {
	if (!delta) return;
	var cosRadius = cos(radius), sinRadius = sin(radius), step = direction * delta;
	if (t0 == null) {
		t0 = radius + direction * tau;
		t1 = radius - step / 2;
	} else {
		t0 = circleRadius(cosRadius, t0);
		t1 = circleRadius(cosRadius, t1);
		if (direction > 0 ? t0 < t1 : t0 > t1) t0 += direction * tau;
	}
	for (var point, t = t0; direction > 0 ? t > t1 : t < t1; t -= step) {
		point = spherical([
			cosRadius,
			-sinRadius * cos(t),
			-sinRadius * sin(t)
		]);
		stream.point(point[0], point[1]);
	}
}
function circleRadius(cosRadius, point) {
	point = cartesian(point), point[0] -= cosRadius;
	cartesianNormalizeInPlace(point);
	var radius = acos(-point[1]);
	return ((-point[2] < 0 ? -radius : radius) + tau - epsilon) % tau;
}
function circle_default$1() {
	var center = constant_default$1([0, 0]), radius = constant_default$1(90), precision = constant_default$1(6), ring, rotate, stream = { point };
	function point(x, y) {
		ring.push(x = rotate(x, y));
		x[0] *= degrees, x[1] *= degrees;
	}
	function circle() {
		var c = center.apply(this, arguments), r = radius.apply(this, arguments) * radians, p = precision.apply(this, arguments) * radians;
		ring = [];
		rotate = rotateRadians(-c[0] * radians, -c[1] * radians, 0).invert;
		circleStream(stream, r, p, 1);
		c = {
			type: "Polygon",
			coordinates: [ring]
		};
		ring = rotate = null;
		return c;
	}
	circle.center = function(_) {
		return arguments.length ? (center = typeof _ === "function" ? _ : constant_default$1([+_[0], +_[1]]), circle) : center;
	};
	circle.radius = function(_) {
		return arguments.length ? (radius = typeof _ === "function" ? _ : constant_default$1(+_), circle) : radius;
	};
	circle.precision = function(_) {
		return arguments.length ? (precision = typeof _ === "function" ? _ : constant_default$1(+_), circle) : precision;
	};
	return circle;
}
var init_circle$1 = __esmMin((() => {
	init_cartesian();
	init_constant$1();
	init_math();
	init_rotation();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/buffer.js
function buffer_default() {
	var lines = [], line;
	return {
		point: function(x, y, m) {
			line.push([
				x,
				y,
				m
			]);
		},
		lineStart: function() {
			lines.push(line = []);
		},
		lineEnd: noop,
		rejoin: function() {
			if (lines.length > 1) lines.push(lines.pop().concat(lines.shift()));
		},
		result: function() {
			var result = lines;
			lines = [];
			line = null;
			return result;
		}
	};
}
var init_buffer = __esmMin((() => {
	init_noop();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/pointEqual.js
function pointEqual_default(a, b) {
	return abs(a[0] - b[0]) < 1e-6 && abs(a[1] - b[1]) < 1e-6;
}
var init_pointEqual = __esmMin((() => {
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/rejoin.js
function Intersection(point, points, other, entry) {
	this.x = point;
	this.z = points;
	this.o = other;
	this.e = entry;
	this.v = false;
	this.n = this.p = null;
}
function rejoin_default(segments, compareIntersection, startInside, interpolate, stream) {
	var subject = [], clip = [], i, n;
	segments.forEach(function(segment) {
		if ((n = segment.length - 1) <= 0) return;
		var n, p0 = segment[0], p1 = segment[n], x;
		if (pointEqual_default(p0, p1)) {
			if (!p0[2] && !p1[2]) {
				stream.lineStart();
				for (i = 0; i < n; ++i) stream.point((p0 = segment[i])[0], p0[1]);
				stream.lineEnd();
				return;
			}
			p1[0] += 2 * epsilon;
		}
		subject.push(x = new Intersection(p0, segment, null, true));
		clip.push(x.o = new Intersection(p0, null, x, false));
		subject.push(x = new Intersection(p1, segment, null, false));
		clip.push(x.o = new Intersection(p1, null, x, true));
	});
	if (!subject.length) return;
	clip.sort(compareIntersection);
	link(subject);
	link(clip);
	for (i = 0, n = clip.length; i < n; ++i) clip[i].e = startInside = !startInside;
	var start = subject[0], points, point;
	while (1) {
		var current = start, isSubject = true;
		while (current.v) if ((current = current.n) === start) return;
		points = current.z;
		stream.lineStart();
		do {
			current.v = current.o.v = true;
			if (current.e) {
				if (isSubject) for (i = 0, n = points.length; i < n; ++i) stream.point((point = points[i])[0], point[1]);
				else interpolate(current.x, current.n.x, 1, stream);
				current = current.n;
			} else {
				if (isSubject) {
					points = current.p.z;
					for (i = points.length - 1; i >= 0; --i) stream.point((point = points[i])[0], point[1]);
				} else interpolate(current.x, current.p.x, -1, stream);
				current = current.p;
			}
			current = current.o;
			points = current.z;
			isSubject = !isSubject;
		} while (!current.v);
		stream.lineEnd();
	}
}
function link(array) {
	if (!(n = array.length)) return;
	var n, i = 0, a = array[0], b;
	while (++i < n) {
		a.n = b = array[i];
		b.p = a;
		a = b;
	}
	a.n = b = array[0];
	b.p = a;
}
var init_rejoin = __esmMin((() => {
	init_pointEqual();
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/polygonContains.js
function longitude(point) {
	if (abs(point[0]) <= pi) return point[0];
	else return sign(point[0]) * ((abs(point[0]) + pi) % tau - pi);
}
function polygonContains_default(polygon, point) {
	var lambda = longitude(point), phi = point[1], sinPhi = sin(phi), normal = [
		sin(lambda),
		-cos(lambda),
		0
	], angle = 0, winding = 0;
	var sum = new Adder();
	if (sinPhi === 1) phi = halfPi + epsilon;
	else if (sinPhi === -1) phi = -halfPi - epsilon;
	for (var i = 0, n = polygon.length; i < n; ++i) {
		if (!(m = (ring = polygon[i]).length)) continue;
		var ring, m, point0 = ring[m - 1], lambda0 = longitude(point0), phi0 = point0[1] / 2 + quarterPi, sinPhi0 = sin(phi0), cosPhi0 = cos(phi0);
		for (var j = 0; j < m; ++j, lambda0 = lambda1, sinPhi0 = sinPhi1, cosPhi0 = cosPhi1, point0 = point1) {
			var point1 = ring[j], lambda1 = longitude(point1), phi1 = point1[1] / 2 + quarterPi, sinPhi1 = sin(phi1), cosPhi1 = cos(phi1), delta = lambda1 - lambda0, sign = delta >= 0 ? 1 : -1, absDelta = sign * delta, antimeridian = absDelta > pi, k = sinPhi0 * sinPhi1;
			sum.add(atan2(k * sign * sin(absDelta), cosPhi0 * cosPhi1 + k * cos(absDelta)));
			angle += antimeridian ? delta + sign * tau : delta;
			if (antimeridian ^ lambda0 >= lambda ^ lambda1 >= lambda) {
				var arc = cartesianCross(cartesian(point0), cartesian(point1));
				cartesianNormalizeInPlace(arc);
				var intersection = cartesianCross(normal, arc);
				cartesianNormalizeInPlace(intersection);
				var phiArc = (antimeridian ^ delta >= 0 ? -1 : 1) * asin(intersection[2]);
				if (phi > phiArc || phi === phiArc && (arc[0] || arc[1])) winding += antimeridian ^ delta >= 0 ? 1 : -1;
			}
		}
	}
	return (angle < -1e-6 || angle < 1e-6 && sum < -1e-12) ^ winding & 1;
}
var init_polygonContains = __esmMin((() => {
	init_src$2();
	init_cartesian();
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/index.js
function clip_default(pointVisible, clipLine, interpolate, start) {
	return function(sink) {
		var line = clipLine(sink), ringBuffer = buffer_default(), ringSink = clipLine(ringBuffer), polygonStarted = false, polygon, segments, ring;
		var clip = {
			point,
			lineStart,
			lineEnd,
			polygonStart: function() {
				clip.point = pointRing;
				clip.lineStart = ringStart;
				clip.lineEnd = ringEnd;
				segments = [];
				polygon = [];
			},
			polygonEnd: function() {
				clip.point = point;
				clip.lineStart = lineStart;
				clip.lineEnd = lineEnd;
				segments = merge(segments);
				var startInside = polygonContains_default(polygon, start);
				if (segments.length) {
					if (!polygonStarted) sink.polygonStart(), polygonStarted = true;
					rejoin_default(segments, compareIntersection, startInside, interpolate, sink);
				} else if (startInside) {
					if (!polygonStarted) sink.polygonStart(), polygonStarted = true;
					sink.lineStart();
					interpolate(null, null, 1, sink);
					sink.lineEnd();
				}
				if (polygonStarted) sink.polygonEnd(), polygonStarted = false;
				segments = polygon = null;
			},
			sphere: function() {
				sink.polygonStart();
				sink.lineStart();
				interpolate(null, null, 1, sink);
				sink.lineEnd();
				sink.polygonEnd();
			}
		};
		function point(lambda, phi) {
			if (pointVisible(lambda, phi)) sink.point(lambda, phi);
		}
		function pointLine(lambda, phi) {
			line.point(lambda, phi);
		}
		function lineStart() {
			clip.point = pointLine;
			line.lineStart();
		}
		function lineEnd() {
			clip.point = point;
			line.lineEnd();
		}
		function pointRing(lambda, phi) {
			ring.push([lambda, phi]);
			ringSink.point(lambda, phi);
		}
		function ringStart() {
			ringSink.lineStart();
			ring = [];
		}
		function ringEnd() {
			pointRing(ring[0][0], ring[0][1]);
			ringSink.lineEnd();
			var clean = ringSink.clean(), ringSegments = ringBuffer.result(), i, n = ringSegments.length, m, segment, point;
			ring.pop();
			polygon.push(ring);
			ring = null;
			if (!n) return;
			if (clean & 1) {
				segment = ringSegments[0];
				if ((m = segment.length - 1) > 0) {
					if (!polygonStarted) sink.polygonStart(), polygonStarted = true;
					sink.lineStart();
					for (i = 0; i < m; ++i) sink.point((point = segment[i])[0], point[1]);
					sink.lineEnd();
				}
				return;
			}
			if (n > 1 && clean & 2) ringSegments.push(ringSegments.pop().concat(ringSegments.shift()));
			segments.push(ringSegments.filter(validSegment));
		}
		return clip;
	};
}
function validSegment(segment) {
	return segment.length > 1;
}
function compareIntersection(a, b) {
	return ((a = a.x)[0] < 0 ? a[1] - halfPi - epsilon : halfPi - a[1]) - ((b = b.x)[0] < 0 ? b[1] - halfPi - epsilon : halfPi - b[1]);
}
var init_clip = __esmMin((() => {
	init_buffer();
	init_rejoin();
	init_math();
	init_polygonContains();
	init_src$2();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/antimeridian.js
function clipAntimeridianLine(stream) {
	var lambda0 = NaN, phi0 = NaN, sign0 = NaN, clean;
	return {
		lineStart: function() {
			stream.lineStart();
			clean = 1;
		},
		point: function(lambda1, phi1) {
			var sign1 = lambda1 > 0 ? pi : -pi, delta = abs(lambda1 - lambda0);
			if (abs(delta - pi) < 1e-6) {
				stream.point(lambda0, phi0 = (phi0 + phi1) / 2 > 0 ? halfPi : -halfPi);
				stream.point(sign0, phi0);
				stream.lineEnd();
				stream.lineStart();
				stream.point(sign1, phi0);
				stream.point(lambda1, phi0);
				clean = 0;
			} else if (sign0 !== sign1 && delta >= pi) {
				if (abs(lambda0 - sign0) < 1e-6) lambda0 -= sign0 * epsilon;
				if (abs(lambda1 - sign1) < 1e-6) lambda1 -= sign1 * epsilon;
				phi0 = clipAntimeridianIntersect(lambda0, phi0, lambda1, phi1);
				stream.point(sign0, phi0);
				stream.lineEnd();
				stream.lineStart();
				stream.point(sign1, phi0);
				clean = 0;
			}
			stream.point(lambda0 = lambda1, phi0 = phi1);
			sign0 = sign1;
		},
		lineEnd: function() {
			stream.lineEnd();
			lambda0 = phi0 = NaN;
		},
		clean: function() {
			return 2 - clean;
		}
	};
}
function clipAntimeridianIntersect(lambda0, phi0, lambda1, phi1) {
	var cosPhi0, cosPhi1, sinLambda0Lambda1 = sin(lambda0 - lambda1);
	return abs(sinLambda0Lambda1) > 1e-6 ? atan((sin(phi0) * (cosPhi1 = cos(phi1)) * sin(lambda1) - sin(phi1) * (cosPhi0 = cos(phi0)) * sin(lambda0)) / (cosPhi0 * cosPhi1 * sinLambda0Lambda1)) : (phi0 + phi1) / 2;
}
function clipAntimeridianInterpolate(from, to, direction, stream) {
	var phi;
	if (from == null) {
		phi = direction * halfPi;
		stream.point(-pi, phi);
		stream.point(0, phi);
		stream.point(pi, phi);
		stream.point(pi, 0);
		stream.point(pi, -phi);
		stream.point(0, -phi);
		stream.point(-pi, -phi);
		stream.point(-pi, 0);
		stream.point(-pi, phi);
	} else if (abs(from[0] - to[0]) > 1e-6) {
		var lambda = from[0] < to[0] ? pi : -pi;
		phi = direction * lambda / 2;
		stream.point(-lambda, phi);
		stream.point(0, phi);
		stream.point(lambda, phi);
	} else stream.point(to[0], to[1]);
}
var antimeridian_default;
var init_antimeridian = __esmMin((() => {
	init_clip();
	init_math();
	antimeridian_default = clip_default(function() {
		return true;
	}, clipAntimeridianLine, clipAntimeridianInterpolate, [-pi, -halfPi]);
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/circle.js
function circle_default(radius) {
	var cr = cos(radius), delta = 6 * radians, smallRadius = cr > 0, notHemisphere = abs(cr) > epsilon;
	function interpolate(from, to, direction, stream) {
		circleStream(stream, radius, delta, direction, from, to);
	}
	function visible(lambda, phi) {
		return cos(lambda) * cos(phi) > cr;
	}
	function clipLine(stream) {
		var point0, c0, v0, v00, clean;
		return {
			lineStart: function() {
				v00 = v0 = false;
				clean = 1;
			},
			point: function(lambda, phi) {
				var point1 = [lambda, phi], point2, v = visible(lambda, phi), c = smallRadius ? v ? 0 : code(lambda, phi) : v ? code(lambda + (lambda < 0 ? pi : -pi), phi) : 0;
				if (!point0 && (v00 = v0 = v)) stream.lineStart();
				if (v !== v0) {
					point2 = intersect(point0, point1);
					if (!point2 || pointEqual_default(point0, point2) || pointEqual_default(point1, point2)) point1[2] = 1;
				}
				if (v !== v0) {
					clean = 0;
					if (v) {
						stream.lineStart();
						point2 = intersect(point1, point0);
						stream.point(point2[0], point2[1]);
					} else {
						point2 = intersect(point0, point1);
						stream.point(point2[0], point2[1], 2);
						stream.lineEnd();
					}
					point0 = point2;
				} else if (notHemisphere && point0 && smallRadius ^ v) {
					var t;
					if (!(c & c0) && (t = intersect(point1, point0, true))) {
						clean = 0;
						if (smallRadius) {
							stream.lineStart();
							stream.point(t[0][0], t[0][1]);
							stream.point(t[1][0], t[1][1]);
							stream.lineEnd();
						} else {
							stream.point(t[1][0], t[1][1]);
							stream.lineEnd();
							stream.lineStart();
							stream.point(t[0][0], t[0][1], 3);
						}
					}
				}
				if (v && (!point0 || !pointEqual_default(point0, point1))) stream.point(point1[0], point1[1]);
				point0 = point1, v0 = v, c0 = c;
			},
			lineEnd: function() {
				if (v0) stream.lineEnd();
				point0 = null;
			},
			clean: function() {
				return clean | (v00 && v0) << 1;
			}
		};
	}
	function intersect(a, b, two) {
		var pa = cartesian(a), pb = cartesian(b);
		var n1 = [
			1,
			0,
			0
		], n2 = cartesianCross(pa, pb), n2n2 = cartesianDot(n2, n2), n1n2 = n2[0], determinant = n2n2 - n1n2 * n1n2;
		if (!determinant) return !two && a;
		var c1 = cr * n2n2 / determinant, c2 = -cr * n1n2 / determinant, n1xn2 = cartesianCross(n1, n2), A = cartesianScale(n1, c1);
		cartesianAddInPlace(A, cartesianScale(n2, c2));
		var u = n1xn2, w = cartesianDot(A, u), uu = cartesianDot(u, u), t2 = w * w - uu * (cartesianDot(A, A) - 1);
		if (t2 < 0) return;
		var t = sqrt(t2), q = cartesianScale(u, (-w - t) / uu);
		cartesianAddInPlace(q, A);
		q = spherical(q);
		if (!two) return q;
		var lambda0 = a[0], lambda1 = b[0], phi0 = a[1], phi1 = b[1], z;
		if (lambda1 < lambda0) z = lambda0, lambda0 = lambda1, lambda1 = z;
		var delta = lambda1 - lambda0, polar = abs(delta - pi) < epsilon, meridian = polar || delta < 1e-6;
		if (!polar && phi1 < phi0) z = phi0, phi0 = phi1, phi1 = z;
		if (meridian ? polar ? phi0 + phi1 > 0 ^ q[1] < (abs(q[0] - lambda0) < 1e-6 ? phi0 : phi1) : phi0 <= q[1] && q[1] <= phi1 : delta > pi ^ (lambda0 <= q[0] && q[0] <= lambda1)) {
			var q1 = cartesianScale(u, (-w + t) / uu);
			cartesianAddInPlace(q1, A);
			return [q, spherical(q1)];
		}
	}
	function code(lambda, phi) {
		var r = smallRadius ? radius : pi - radius, code = 0;
		if (lambda < -r) code |= 1;
		else if (lambda > r) code |= 2;
		if (phi < -r) code |= 4;
		else if (phi > r) code |= 8;
		return code;
	}
	return clip_default(visible, clipLine, interpolate, smallRadius ? [0, -radius] : [-pi, radius - pi]);
}
var init_circle = __esmMin((() => {
	init_cartesian();
	init_circle$1();
	init_math();
	init_pointEqual();
	init_clip();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/line.js
function line_default(a, b, x0, y0, x1, y1) {
	var ax = a[0], ay = a[1], bx = b[0], by = b[1], t0 = 0, t1 = 1, dx = bx - ax, dy = by - ay, r = x0 - ax;
	if (!dx && r > 0) return;
	r /= dx;
	if (dx < 0) {
		if (r < t0) return;
		if (r < t1) t1 = r;
	} else if (dx > 0) {
		if (r > t1) return;
		if (r > t0) t0 = r;
	}
	r = x1 - ax;
	if (!dx && r < 0) return;
	r /= dx;
	if (dx < 0) {
		if (r > t1) return;
		if (r > t0) t0 = r;
	} else if (dx > 0) {
		if (r < t0) return;
		if (r < t1) t1 = r;
	}
	r = y0 - ay;
	if (!dy && r > 0) return;
	r /= dy;
	if (dy < 0) {
		if (r < t0) return;
		if (r < t1) t1 = r;
	} else if (dy > 0) {
		if (r > t1) return;
		if (r > t0) t0 = r;
	}
	r = y1 - ay;
	if (!dy && r < 0) return;
	r /= dy;
	if (dy < 0) {
		if (r > t1) return;
		if (r > t0) t0 = r;
	} else if (dy > 0) {
		if (r < t0) return;
		if (r < t1) t1 = r;
	}
	if (t0 > 0) a[0] = ax + t0 * dx, a[1] = ay + t0 * dy;
	if (t1 < 1) b[0] = ax + t1 * dx, b[1] = ay + t1 * dy;
	return true;
}
var init_line = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/rectangle.js
function clipRectangle(x0, y0, x1, y1) {
	function visible(x, y) {
		return x0 <= x && x <= x1 && y0 <= y && y <= y1;
	}
	function interpolate(from, to, direction, stream) {
		var a = 0, a1 = 0;
		if (from == null || (a = corner(from, direction)) !== (a1 = corner(to, direction)) || comparePoint(from, to) < 0 ^ direction > 0) do
			stream.point(a === 0 || a === 3 ? x0 : x1, a > 1 ? y1 : y0);
		while ((a = (a + direction + 4) % 4) !== a1);
		else stream.point(to[0], to[1]);
	}
	function corner(p, direction) {
		return abs(p[0] - x0) < 1e-6 ? direction > 0 ? 0 : 3 : abs(p[0] - x1) < 1e-6 ? direction > 0 ? 2 : 1 : abs(p[1] - y0) < 1e-6 ? direction > 0 ? 1 : 0 : direction > 0 ? 3 : 2;
	}
	function compareIntersection(a, b) {
		return comparePoint(a.x, b.x);
	}
	function comparePoint(a, b) {
		var ca = corner(a, 1), cb = corner(b, 1);
		return ca !== cb ? ca - cb : ca === 0 ? b[1] - a[1] : ca === 1 ? a[0] - b[0] : ca === 2 ? a[1] - b[1] : b[0] - a[0];
	}
	return function(stream) {
		var activeStream = stream, bufferStream = buffer_default(), segments, polygon, ring, x__, y__, v__, x_, y_, v_, first, clean;
		var clipStream = {
			point,
			lineStart,
			lineEnd,
			polygonStart,
			polygonEnd
		};
		function point(x, y) {
			if (visible(x, y)) activeStream.point(x, y);
		}
		function polygonInside() {
			var winding = 0;
			for (var i = 0, n = polygon.length; i < n; ++i) for (var ring = polygon[i], j = 1, m = ring.length, point = ring[0], a0, a1, b0 = point[0], b1 = point[1]; j < m; ++j) {
				a0 = b0, a1 = b1, point = ring[j], b0 = point[0], b1 = point[1];
				if (a1 <= y1) {
					if (b1 > y1 && (b0 - a0) * (y1 - a1) > (b1 - a1) * (x0 - a0)) ++winding;
				} else if (b1 <= y1 && (b0 - a0) * (y1 - a1) < (b1 - a1) * (x0 - a0)) --winding;
			}
			return winding;
		}
		function polygonStart() {
			activeStream = bufferStream, segments = [], polygon = [], clean = true;
		}
		function polygonEnd() {
			var startInside = polygonInside(), cleanInside = clean && startInside, visible = (segments = merge(segments)).length;
			if (cleanInside || visible) {
				stream.polygonStart();
				if (cleanInside) {
					stream.lineStart();
					interpolate(null, null, 1, stream);
					stream.lineEnd();
				}
				if (visible) rejoin_default(segments, compareIntersection, startInside, interpolate, stream);
				stream.polygonEnd();
			}
			activeStream = stream, segments = polygon = ring = null;
		}
		function lineStart() {
			clipStream.point = linePoint;
			if (polygon) polygon.push(ring = []);
			first = true;
			v_ = false;
			x_ = y_ = NaN;
		}
		function lineEnd() {
			if (segments) {
				linePoint(x__, y__);
				if (v__ && v_) bufferStream.rejoin();
				segments.push(bufferStream.result());
			}
			clipStream.point = point;
			if (v_) activeStream.lineEnd();
		}
		function linePoint(x, y) {
			var v = visible(x, y);
			if (polygon) ring.push([x, y]);
			if (first) {
				x__ = x, y__ = y, v__ = v;
				first = false;
				if (v) {
					activeStream.lineStart();
					activeStream.point(x, y);
				}
			} else if (v && v_) activeStream.point(x, y);
			else {
				var a = [x_ = Math.max(clipMin, Math.min(clipMax, x_)), y_ = Math.max(clipMin, Math.min(clipMax, y_))], b = [x = Math.max(clipMin, Math.min(clipMax, x)), y = Math.max(clipMin, Math.min(clipMax, y))];
				if (line_default(a, b, x0, y0, x1, y1)) {
					if (!v_) {
						activeStream.lineStart();
						activeStream.point(a[0], a[1]);
					}
					activeStream.point(b[0], b[1]);
					if (!v) activeStream.lineEnd();
					clean = false;
				} else if (v) {
					activeStream.lineStart();
					activeStream.point(x, y);
					clean = false;
				}
			}
			x_ = x, y_ = y, v_ = v;
		}
		return clipStream;
	};
}
var clipMax, clipMin;
var init_rectangle = __esmMin((() => {
	init_math();
	init_buffer();
	init_line();
	init_rejoin();
	init_src$2();
	clipMax = 1e9, clipMin = -clipMax;
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/clip/extent.js
function extent_default() {
	var x0 = 0, y0 = 0, x1 = 960, y1 = 500, cache, cacheStream, clip;
	return clip = {
		stream: function(stream) {
			return cache && cacheStream === stream ? cache : cache = clipRectangle(x0, y0, x1, y1)(cacheStream = stream);
		},
		extent: function(_) {
			return arguments.length ? (x0 = +_[0][0], y0 = +_[0][1], x1 = +_[1][0], y1 = +_[1][1], cache = cacheStream = null, clip) : [[x0, y0], [x1, y1]];
		}
	};
}
var init_extent = __esmMin((() => {
	init_rectangle();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/length.js
function lengthLineStart() {
	lengthStream$1.point = lengthPointFirst$1;
	lengthStream$1.lineEnd = lengthLineEnd;
}
function lengthLineEnd() {
	lengthStream$1.point = lengthStream$1.lineEnd = noop;
}
function lengthPointFirst$1(lambda, phi) {
	lambda *= radians, phi *= radians;
	lambda0 = lambda, sinPhi0 = sin(phi), cosPhi0 = cos(phi);
	lengthStream$1.point = lengthPoint$1;
}
function lengthPoint$1(lambda, phi) {
	lambda *= radians, phi *= radians;
	var sinPhi = sin(phi), cosPhi = cos(phi), delta = abs(lambda - lambda0), cosDelta = cos(delta), x = cosPhi * sin(delta), y = cosPhi0 * sinPhi - sinPhi0 * cosPhi * cosDelta, z = sinPhi0 * sinPhi + cosPhi0 * cosPhi * cosDelta;
	lengthSum$1.add(atan2(sqrt(x * x + y * y), z));
	lambda0 = lambda, sinPhi0 = sinPhi, cosPhi0 = cosPhi;
}
function length_default(object) {
	lengthSum$1 = new Adder();
	stream_default(object, lengthStream$1);
	return +lengthSum$1;
}
var lengthSum$1, lambda0, sinPhi0, cosPhi0, lengthStream$1;
var init_length = __esmMin((() => {
	init_src$2();
	init_math();
	init_noop();
	init_stream();
	lengthStream$1 = {
		sphere: noop,
		point: noop,
		lineStart: lengthLineStart,
		lineEnd: noop,
		polygonStart: noop,
		polygonEnd: noop
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/distance.js
function distance_default(a, b) {
	coordinates[0] = a;
	coordinates[1] = b;
	return length_default(object);
}
var coordinates, object;
var init_distance = __esmMin((() => {
	init_length();
	coordinates = [null, null], object = {
		type: "LineString",
		coordinates
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/contains.js
function containsGeometry(geometry, point) {
	return geometry && containsGeometryType.hasOwnProperty(geometry.type) ? containsGeometryType[geometry.type](geometry, point) : false;
}
function containsPoint(coordinates, point) {
	return distance_default(coordinates, point) === 0;
}
function containsLine(coordinates, point) {
	var ao, bo, ab;
	for (var i = 0, n = coordinates.length; i < n; i++) {
		bo = distance_default(coordinates[i], point);
		if (bo === 0) return true;
		if (i > 0) {
			ab = distance_default(coordinates[i], coordinates[i - 1]);
			if (ab > 0 && ao <= ab && bo <= ab && (ao + bo - ab) * (1 - Math.pow((ao - bo) / ab, 2)) < 1e-12 * ab) return true;
		}
		ao = bo;
	}
	return false;
}
function containsPolygon(coordinates, point) {
	return !!polygonContains_default(coordinates.map(ringRadians), pointRadians(point));
}
function ringRadians(ring) {
	return ring = ring.map(pointRadians), ring.pop(), ring;
}
function pointRadians(point) {
	return [point[0] * radians, point[1] * radians];
}
function contains_default(object, point) {
	return (object && containsObjectType.hasOwnProperty(object.type) ? containsObjectType[object.type] : containsGeometry)(object, point);
}
var containsObjectType, containsGeometryType;
var init_contains = __esmMin((() => {
	init_polygonContains();
	init_distance();
	init_math();
	containsObjectType = {
		Feature: function(object, point) {
			return containsGeometry(object.geometry, point);
		},
		FeatureCollection: function(object, point) {
			var features = object.features, i = -1, n = features.length;
			while (++i < n) if (containsGeometry(features[i].geometry, point)) return true;
			return false;
		}
	};
	containsGeometryType = {
		Sphere: function() {
			return true;
		},
		Point: function(object, point) {
			return containsPoint(object.coordinates, point);
		},
		MultiPoint: function(object, point) {
			var coordinates = object.coordinates, i = -1, n = coordinates.length;
			while (++i < n) if (containsPoint(coordinates[i], point)) return true;
			return false;
		},
		LineString: function(object, point) {
			return containsLine(object.coordinates, point);
		},
		MultiLineString: function(object, point) {
			var coordinates = object.coordinates, i = -1, n = coordinates.length;
			while (++i < n) if (containsLine(coordinates[i], point)) return true;
			return false;
		},
		Polygon: function(object, point) {
			return containsPolygon(object.coordinates, point);
		},
		MultiPolygon: function(object, point) {
			var coordinates = object.coordinates, i = -1, n = coordinates.length;
			while (++i < n) if (containsPolygon(coordinates[i], point)) return true;
			return false;
		},
		GeometryCollection: function(object, point) {
			var geometries = object.geometries, i = -1, n = geometries.length;
			while (++i < n) if (containsGeometry(geometries[i], point)) return true;
			return false;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/graticule.js
function graticuleX(y0, y1, dy) {
	var y = range_default(y0, y1 - epsilon, dy).concat(y1);
	return function(x) {
		return y.map(function(y) {
			return [x, y];
		});
	};
}
function graticuleY(x0, x1, dx) {
	var x = range_default(x0, x1 - epsilon, dx).concat(x1);
	return function(y) {
		return x.map(function(x) {
			return [x, y];
		});
	};
}
function graticule() {
	var x1, x0, X1, X0, y1, y0, Y1, Y0, dx = 10, dy = dx, DX = 90, DY = 360, x, y, X, Y, precision = 2.5;
	function graticule() {
		return {
			type: "MultiLineString",
			coordinates: lines()
		};
	}
	function lines() {
		return range_default(ceil(X0 / DX) * DX, X1, DX).map(X).concat(range_default(ceil(Y0 / DY) * DY, Y1, DY).map(Y)).concat(range_default(ceil(x0 / dx) * dx, x1, dx).filter(function(x) {
			return abs(x % DX) > epsilon;
		}).map(x)).concat(range_default(ceil(y0 / dy) * dy, y1, dy).filter(function(y) {
			return abs(y % DY) > epsilon;
		}).map(y));
	}
	graticule.lines = function() {
		return lines().map(function(coordinates) {
			return {
				type: "LineString",
				coordinates
			};
		});
	};
	graticule.outline = function() {
		return {
			type: "Polygon",
			coordinates: [X(X0).concat(Y(Y1).slice(1), X(X1).reverse().slice(1), Y(Y0).reverse().slice(1))]
		};
	};
	graticule.extent = function(_) {
		if (!arguments.length) return graticule.extentMinor();
		return graticule.extentMajor(_).extentMinor(_);
	};
	graticule.extentMajor = function(_) {
		if (!arguments.length) return [[X0, Y0], [X1, Y1]];
		X0 = +_[0][0], X1 = +_[1][0];
		Y0 = +_[0][1], Y1 = +_[1][1];
		if (X0 > X1) _ = X0, X0 = X1, X1 = _;
		if (Y0 > Y1) _ = Y0, Y0 = Y1, Y1 = _;
		return graticule.precision(precision);
	};
	graticule.extentMinor = function(_) {
		if (!arguments.length) return [[x0, y0], [x1, y1]];
		x0 = +_[0][0], x1 = +_[1][0];
		y0 = +_[0][1], y1 = +_[1][1];
		if (x0 > x1) _ = x0, x0 = x1, x1 = _;
		if (y0 > y1) _ = y0, y0 = y1, y1 = _;
		return graticule.precision(precision);
	};
	graticule.step = function(_) {
		if (!arguments.length) return graticule.stepMinor();
		return graticule.stepMajor(_).stepMinor(_);
	};
	graticule.stepMajor = function(_) {
		if (!arguments.length) return [DX, DY];
		DX = +_[0], DY = +_[1];
		return graticule;
	};
	graticule.stepMinor = function(_) {
		if (!arguments.length) return [dx, dy];
		dx = +_[0], dy = +_[1];
		return graticule;
	};
	graticule.precision = function(_) {
		if (!arguments.length) return precision;
		precision = +_;
		x = graticuleX(y0, y1, 90);
		y = graticuleY(x0, x1, precision);
		X = graticuleX(Y0, Y1, 90);
		Y = graticuleY(X0, X1, precision);
		return graticule;
	};
	return graticule.extentMajor([[-180, -90 + epsilon], [180, 90 - epsilon]]).extentMinor([[-180, -80 - epsilon], [180, 80 + epsilon]]);
}
function graticule10() {
	return graticule()();
}
var init_graticule = __esmMin((() => {
	init_src$2();
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/interpolate.js
function interpolate_default(a, b) {
	var x0 = a[0] * radians, y0 = a[1] * radians, x1 = b[0] * radians, y1 = b[1] * radians, cy0 = cos(y0), sy0 = sin(y0), cy1 = cos(y1), sy1 = sin(y1), kx0 = cy0 * cos(x0), ky0 = cy0 * sin(x0), kx1 = cy1 * cos(x1), ky1 = cy1 * sin(x1), d = 2 * asin(sqrt(haversin(y1 - y0) + cy0 * cy1 * haversin(x1 - x0))), k = sin(d);
	var interpolate = d ? function(t) {
		var B = sin(t *= d) / k, A = sin(d - t) / k, x = A * kx0 + B * kx1, y = A * ky0 + B * ky1, z = A * sy0 + B * sy1;
		return [atan2(y, x) * degrees, atan2(z, sqrt(x * x + y * y)) * degrees];
	} : function() {
		return [x0 * degrees, y0 * degrees];
	};
	interpolate.distance = d;
	return interpolate;
}
var init_interpolate = __esmMin((() => {
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/identity.js
var identity_default$1;
var init_identity$1 = __esmMin((() => {
	identity_default$1 = (x) => x;
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/area.js
function areaRingStart() {
	areaStream.point = areaPointFirst;
}
function areaPointFirst(x, y) {
	areaStream.point = areaPoint;
	x00$2 = x0$3 = x, y00$2 = y0$3 = y;
}
function areaPoint(x, y) {
	areaRingSum.add(y0$3 * x - x0$3 * y);
	x0$3 = x, y0$3 = y;
}
function areaRingEnd() {
	areaPoint(x00$2, y00$2);
}
var areaSum, areaRingSum, x00$2, y00$2, x0$3, y0$3, areaStream;
var init_area = __esmMin((() => {
	init_src$2();
	init_math();
	init_noop();
	areaSum = new Adder(), areaRingSum = new Adder();
	areaStream = {
		point: noop,
		lineStart: noop,
		lineEnd: noop,
		polygonStart: function() {
			areaStream.lineStart = areaRingStart;
			areaStream.lineEnd = areaRingEnd;
		},
		polygonEnd: function() {
			areaStream.lineStart = areaStream.lineEnd = areaStream.point = noop;
			areaSum.add(abs(areaRingSum));
			areaRingSum = new Adder();
		},
		result: function() {
			var area = areaSum / 2;
			areaSum = new Adder();
			return area;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/bounds.js
function boundsPoint(x, y) {
	if (x < x0$2) x0$2 = x;
	if (x > x1) x1 = x;
	if (y < y0$2) y0$2 = y;
	if (y > y1) y1 = y;
}
var x0$2, y0$2, x1, y1, boundsStream;
var init_bounds = __esmMin((() => {
	init_noop();
	x0$2 = Infinity, y0$2 = x0$2, x1 = -x0$2, y1 = x1;
	boundsStream = {
		point: boundsPoint,
		lineStart: noop,
		lineEnd: noop,
		polygonStart: noop,
		polygonEnd: noop,
		result: function() {
			var bounds = [[x0$2, y0$2], [x1, y1]];
			x1 = y1 = -(y0$2 = x0$2 = Infinity);
			return bounds;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/centroid.js
function centroidPoint(x, y) {
	X0 += x;
	Y0 += y;
	++Z0;
}
function centroidLineStart() {
	centroidStream.point = centroidPointFirstLine;
}
function centroidPointFirstLine(x, y) {
	centroidStream.point = centroidPointLine;
	centroidPoint(x0$1 = x, y0$1 = y);
}
function centroidPointLine(x, y) {
	var dx = x - x0$1, dy = y - y0$1, z = sqrt(dx * dx + dy * dy);
	X1 += z * (x0$1 + x) / 2;
	Y1 += z * (y0$1 + y) / 2;
	Z1 += z;
	centroidPoint(x0$1 = x, y0$1 = y);
}
function centroidLineEnd() {
	centroidStream.point = centroidPoint;
}
function centroidRingStart() {
	centroidStream.point = centroidPointFirstRing;
}
function centroidRingEnd() {
	centroidPointRing(x00$1, y00$1);
}
function centroidPointFirstRing(x, y) {
	centroidStream.point = centroidPointRing;
	centroidPoint(x00$1 = x0$1 = x, y00$1 = y0$1 = y);
}
function centroidPointRing(x, y) {
	var dx = x - x0$1, dy = y - y0$1, z = sqrt(dx * dx + dy * dy);
	X1 += z * (x0$1 + x) / 2;
	Y1 += z * (y0$1 + y) / 2;
	Z1 += z;
	z = y0$1 * x - x0$1 * y;
	X2 += z * (x0$1 + x);
	Y2 += z * (y0$1 + y);
	Z2 += z * 3;
	centroidPoint(x0$1 = x, y0$1 = y);
}
var X0, Y0, Z0, X1, Y1, Z1, X2, Y2, Z2, x00$1, y00$1, x0$1, y0$1, centroidStream;
var init_centroid = __esmMin((() => {
	init_math();
	X0 = 0, Y0 = 0, Z0 = 0, X1 = 0, Y1 = 0, Z1 = 0, X2 = 0, Y2 = 0, Z2 = 0;
	centroidStream = {
		point: centroidPoint,
		lineStart: centroidLineStart,
		lineEnd: centroidLineEnd,
		polygonStart: function() {
			centroidStream.lineStart = centroidRingStart;
			centroidStream.lineEnd = centroidRingEnd;
		},
		polygonEnd: function() {
			centroidStream.point = centroidPoint;
			centroidStream.lineStart = centroidLineStart;
			centroidStream.lineEnd = centroidLineEnd;
		},
		result: function() {
			var centroid = Z2 ? [X2 / Z2, Y2 / Z2] : Z1 ? [X1 / Z1, Y1 / Z1] : Z0 ? [X0 / Z0, Y0 / Z0] : [NaN, NaN];
			X0 = Y0 = Z0 = X1 = Y1 = Z1 = X2 = Y2 = Z2 = 0;
			return centroid;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/context.js
function PathContext(context) {
	this._context = context;
}
var init_context = __esmMin((() => {
	init_math();
	init_noop();
	PathContext.prototype = {
		_radius: 4.5,
		pointRadius: function(_) {
			return this._radius = _, this;
		},
		polygonStart: function() {
			this._line = 0;
		},
		polygonEnd: function() {
			this._line = NaN;
		},
		lineStart: function() {
			this._point = 0;
		},
		lineEnd: function() {
			if (this._line === 0) this._context.closePath();
			this._point = NaN;
		},
		point: function(x, y) {
			switch (this._point) {
				case 0:
					this._context.moveTo(x, y);
					this._point = 1;
					break;
				case 1:
					this._context.lineTo(x, y);
					break;
				default:
					this._context.moveTo(x + this._radius, y);
					this._context.arc(x, y, this._radius, 0, tau);
					break;
			}
		},
		result: noop
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/measure.js
function lengthPointFirst(x, y) {
	lengthStream.point = lengthPoint;
	x00 = x0 = x, y00 = y0 = y;
}
function lengthPoint(x, y) {
	x0 -= x, y0 -= y;
	lengthSum.add(sqrt(x0 * x0 + y0 * y0));
	x0 = x, y0 = y;
}
var lengthSum, lengthRing, x00, y00, x0, y0, lengthStream;
var init_measure = __esmMin((() => {
	init_src$2();
	init_math();
	init_noop();
	lengthSum = new Adder();
	lengthStream = {
		point: noop,
		lineStart: function() {
			lengthStream.point = lengthPointFirst;
		},
		lineEnd: function() {
			if (lengthRing) lengthPoint(x00, y00);
			lengthStream.point = noop;
		},
		polygonStart: function() {
			lengthRing = true;
		},
		polygonEnd: function() {
			lengthRing = null;
		},
		result: function() {
			var length = +lengthSum;
			lengthSum = new Adder();
			return length;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/string.js
function PathString() {
	this._string = [];
}
function circle(radius) {
	return "m0," + radius + "a" + radius + "," + radius + " 0 1,1 0," + -2 * radius + "a" + radius + "," + radius + " 0 1,1 0," + 2 * radius + "z";
}
var init_string = __esmMin((() => {
	PathString.prototype = {
		_radius: 4.5,
		_circle: circle(4.5),
		pointRadius: function(_) {
			if ((_ = +_) !== this._radius) this._radius = _, this._circle = null;
			return this;
		},
		polygonStart: function() {
			this._line = 0;
		},
		polygonEnd: function() {
			this._line = NaN;
		},
		lineStart: function() {
			this._point = 0;
		},
		lineEnd: function() {
			if (this._line === 0) this._string.push("Z");
			this._point = NaN;
		},
		point: function(x, y) {
			switch (this._point) {
				case 0:
					this._string.push("M", x, ",", y);
					this._point = 1;
					break;
				case 1:
					this._string.push("L", x, ",", y);
					break;
				default:
					if (this._circle == null) this._circle = circle(this._radius);
					this._string.push("M", x, ",", y, this._circle);
					break;
			}
		},
		result: function() {
			if (this._string.length) {
				var result = this._string.join("");
				this._string = [];
				return result;
			} else return null;
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/path/index.js
function path_default(projection, context) {
	var pointRadius = 4.5, projectionStream, contextStream;
	function path(object) {
		if (object) {
			if (typeof pointRadius === "function") contextStream.pointRadius(+pointRadius.apply(this, arguments));
			stream_default(object, projectionStream(contextStream));
		}
		return contextStream.result();
	}
	path.area = function(object) {
		stream_default(object, projectionStream(areaStream));
		return areaStream.result();
	};
	path.measure = function(object) {
		stream_default(object, projectionStream(lengthStream));
		return lengthStream.result();
	};
	path.bounds = function(object) {
		stream_default(object, projectionStream(boundsStream));
		return boundsStream.result();
	};
	path.centroid = function(object) {
		stream_default(object, projectionStream(centroidStream));
		return centroidStream.result();
	};
	path.projection = function(_) {
		return arguments.length ? (projectionStream = _ == null ? (projection = null, identity_default$1) : (projection = _).stream, path) : projection;
	};
	path.context = function(_) {
		if (!arguments.length) return context;
		contextStream = _ == null ? (context = null, new PathString()) : new PathContext(context = _);
		if (typeof pointRadius !== "function") contextStream.pointRadius(pointRadius);
		return path;
	};
	path.pointRadius = function(_) {
		if (!arguments.length) return pointRadius;
		pointRadius = typeof _ === "function" ? _ : (contextStream.pointRadius(+_), +_);
		return path;
	};
	return path.projection(projection).context(context);
}
var init_path = __esmMin((() => {
	init_identity$1();
	init_stream();
	init_area();
	init_bounds();
	init_centroid();
	init_context();
	init_measure();
	init_string();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/transform.js
function transform_default(methods) {
	return { stream: transformer(methods) };
}
function transformer(methods) {
	return function(stream) {
		var s = new TransformStream();
		for (var key in methods) s[key] = methods[key];
		s.stream = stream;
		return s;
	};
}
function TransformStream() {}
var init_transform = __esmMin((() => {
	TransformStream.prototype = {
		constructor: TransformStream,
		point: function(x, y) {
			this.stream.point(x, y);
		},
		sphere: function() {
			this.stream.sphere();
		},
		lineStart: function() {
			this.stream.lineStart();
		},
		lineEnd: function() {
			this.stream.lineEnd();
		},
		polygonStart: function() {
			this.stream.polygonStart();
		},
		polygonEnd: function() {
			this.stream.polygonEnd();
		}
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/fit.js
function fit(projection, fitBounds, object) {
	var clip = projection.clipExtent && projection.clipExtent();
	projection.scale(150).translate([0, 0]);
	if (clip != null) projection.clipExtent(null);
	stream_default(object, projection.stream(boundsStream));
	fitBounds(boundsStream.result());
	if (clip != null) projection.clipExtent(clip);
	return projection;
}
function fitExtent(projection, extent, object) {
	return fit(projection, function(b) {
		var w = extent[1][0] - extent[0][0], h = extent[1][1] - extent[0][1], k = Math.min(w / (b[1][0] - b[0][0]), h / (b[1][1] - b[0][1])), x = +extent[0][0] + (w - k * (b[1][0] + b[0][0])) / 2, y = +extent[0][1] + (h - k * (b[1][1] + b[0][1])) / 2;
		projection.scale(150 * k).translate([x, y]);
	}, object);
}
function fitSize(projection, size, object) {
	return fitExtent(projection, [[0, 0], size], object);
}
function fitWidth(projection, width, object) {
	return fit(projection, function(b) {
		var w = +width, k = w / (b[1][0] - b[0][0]), x = (w - k * (b[1][0] + b[0][0])) / 2, y = -k * b[0][1];
		projection.scale(150 * k).translate([x, y]);
	}, object);
}
function fitHeight(projection, height, object) {
	return fit(projection, function(b) {
		var h = +height, k = h / (b[1][1] - b[0][1]), x = -k * b[0][0], y = (h - k * (b[1][1] + b[0][1])) / 2;
		projection.scale(150 * k).translate([x, y]);
	}, object);
}
var init_fit = __esmMin((() => {
	init_stream();
	init_bounds();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/resample.js
function resample_default(project, delta2) {
	return +delta2 ? resample(project, delta2) : resampleNone(project);
}
function resampleNone(project) {
	return transformer({ point: function(x, y) {
		x = project(x, y);
		this.stream.point(x[0], x[1]);
	} });
}
function resample(project, delta2) {
	function resampleLineTo(x0, y0, lambda0, a0, b0, c0, x1, y1, lambda1, a1, b1, c1, depth, stream) {
		var dx = x1 - x0, dy = y1 - y0, d2 = dx * dx + dy * dy;
		if (d2 > 4 * delta2 && depth--) {
			var a = a0 + a1, b = b0 + b1, c = c0 + c1, m = sqrt(a * a + b * b + c * c), phi2 = asin(c /= m), lambda2 = abs(abs(c) - 1) < 1e-6 || abs(lambda0 - lambda1) < 1e-6 ? (lambda0 + lambda1) / 2 : atan2(b, a), p = project(lambda2, phi2), x2 = p[0], y2 = p[1], dx2 = x2 - x0, dy2 = y2 - y0, dz = dy * dx2 - dx * dy2;
			if (dz * dz / d2 > delta2 || abs((dx * dx2 + dy * dy2) / d2 - .5) > .3 || a0 * a1 + b0 * b1 + c0 * c1 < cosMinDistance) {
				resampleLineTo(x0, y0, lambda0, a0, b0, c0, x2, y2, lambda2, a /= m, b /= m, c, depth, stream);
				stream.point(x2, y2);
				resampleLineTo(x2, y2, lambda2, a, b, c, x1, y1, lambda1, a1, b1, c1, depth, stream);
			}
		}
	}
	return function(stream) {
		var lambda00, x00, y00, a00, b00, c00, lambda0, x0, y0, a0, b0, c0;
		var resampleStream = {
			point,
			lineStart,
			lineEnd,
			polygonStart: function() {
				stream.polygonStart();
				resampleStream.lineStart = ringStart;
			},
			polygonEnd: function() {
				stream.polygonEnd();
				resampleStream.lineStart = lineStart;
			}
		};
		function point(x, y) {
			x = project(x, y);
			stream.point(x[0], x[1]);
		}
		function lineStart() {
			x0 = NaN;
			resampleStream.point = linePoint;
			stream.lineStart();
		}
		function linePoint(lambda, phi) {
			var c = cartesian([lambda, phi]), p = project(lambda, phi);
			resampleLineTo(x0, y0, lambda0, a0, b0, c0, x0 = p[0], y0 = p[1], lambda0 = lambda, a0 = c[0], b0 = c[1], c0 = c[2], maxDepth, stream);
			stream.point(x0, y0);
		}
		function lineEnd() {
			resampleStream.point = point;
			stream.lineEnd();
		}
		function ringStart() {
			lineStart();
			resampleStream.point = ringPoint;
			resampleStream.lineEnd = ringEnd;
		}
		function ringPoint(lambda, phi) {
			linePoint(lambda00 = lambda, phi), x00 = x0, y00 = y0, a00 = a0, b00 = b0, c00 = c0;
			resampleStream.point = linePoint;
		}
		function ringEnd() {
			resampleLineTo(x0, y0, lambda0, a0, b0, c0, x00, y00, lambda00, a00, b00, c00, maxDepth, stream);
			resampleStream.lineEnd = lineEnd;
			lineEnd();
		}
		return resampleStream;
	};
}
var maxDepth, cosMinDistance;
var init_resample = __esmMin((() => {
	init_cartesian();
	init_math();
	init_transform();
	maxDepth = 16, cosMinDistance = cos(30 * radians);
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/index.js
function transformRotate(rotate) {
	return transformer({ point: function(x, y) {
		var r = rotate(x, y);
		return this.stream.point(r[0], r[1]);
	} });
}
function scaleTranslate(k, dx, dy, sx, sy) {
	function transform(x, y) {
		x *= sx;
		y *= sy;
		return [dx + k * x, dy - k * y];
	}
	transform.invert = function(x, y) {
		return [(x - dx) / k * sx, (dy - y) / k * sy];
	};
	return transform;
}
function scaleTranslateRotate(k, dx, dy, sx, sy, alpha) {
	if (!alpha) return scaleTranslate(k, dx, dy, sx, sy);
	var cosAlpha = cos(alpha), sinAlpha = sin(alpha), a = cosAlpha * k, b = sinAlpha * k, ai = cosAlpha / k, bi = sinAlpha / k, ci = (sinAlpha * dy - cosAlpha * dx) / k, fi = (sinAlpha * dx + cosAlpha * dy) / k;
	function transform(x, y) {
		x *= sx;
		y *= sy;
		return [a * x - b * y + dx, dy - b * x - a * y];
	}
	transform.invert = function(x, y) {
		return [sx * (ai * x - bi * y + ci), sy * (fi - bi * x - ai * y)];
	};
	return transform;
}
function projection(project) {
	return projectionMutator(function() {
		return project;
	})();
}
function projectionMutator(projectAt) {
	var project, k = 150, x = 480, y = 250, lambda = 0, phi = 0, deltaLambda = 0, deltaPhi = 0, deltaGamma = 0, rotate, alpha = 0, sx = 1, sy = 1, theta = null, preclip = antimeridian_default, x0 = null, y0, x1, y1, postclip = identity_default$1, delta2 = .5, projectResample, projectTransform, projectRotateTransform, cache, cacheStream;
	function projection(point) {
		return projectRotateTransform(point[0] * radians, point[1] * radians);
	}
	function invert(point) {
		point = projectRotateTransform.invert(point[0], point[1]);
		return point && [point[0] * degrees, point[1] * degrees];
	}
	projection.stream = function(stream) {
		return cache && cacheStream === stream ? cache : cache = transformRadians(transformRotate(rotate)(preclip(projectResample(postclip(cacheStream = stream)))));
	};
	projection.preclip = function(_) {
		return arguments.length ? (preclip = _, theta = void 0, reset()) : preclip;
	};
	projection.postclip = function(_) {
		return arguments.length ? (postclip = _, x0 = y0 = x1 = y1 = null, reset()) : postclip;
	};
	projection.clipAngle = function(_) {
		return arguments.length ? (preclip = +_ ? circle_default(theta = _ * radians) : (theta = null, antimeridian_default), reset()) : theta * degrees;
	};
	projection.clipExtent = function(_) {
		return arguments.length ? (postclip = _ == null ? (x0 = y0 = x1 = y1 = null, identity_default$1) : clipRectangle(x0 = +_[0][0], y0 = +_[0][1], x1 = +_[1][0], y1 = +_[1][1]), reset()) : x0 == null ? null : [[x0, y0], [x1, y1]];
	};
	projection.scale = function(_) {
		return arguments.length ? (k = +_, recenter()) : k;
	};
	projection.translate = function(_) {
		return arguments.length ? (x = +_[0], y = +_[1], recenter()) : [x, y];
	};
	projection.center = function(_) {
		return arguments.length ? (lambda = _[0] % 360 * radians, phi = _[1] % 360 * radians, recenter()) : [lambda * degrees, phi * degrees];
	};
	projection.rotate = function(_) {
		return arguments.length ? (deltaLambda = _[0] % 360 * radians, deltaPhi = _[1] % 360 * radians, deltaGamma = _.length > 2 ? _[2] % 360 * radians : 0, recenter()) : [
			deltaLambda * degrees,
			deltaPhi * degrees,
			deltaGamma * degrees
		];
	};
	projection.angle = function(_) {
		return arguments.length ? (alpha = _ % 360 * radians, recenter()) : alpha * degrees;
	};
	projection.reflectX = function(_) {
		return arguments.length ? (sx = _ ? -1 : 1, recenter()) : sx < 0;
	};
	projection.reflectY = function(_) {
		return arguments.length ? (sy = _ ? -1 : 1, recenter()) : sy < 0;
	};
	projection.precision = function(_) {
		return arguments.length ? (projectResample = resample_default(projectTransform, delta2 = _ * _), reset()) : sqrt(delta2);
	};
	projection.fitExtent = function(extent, object) {
		return fitExtent(projection, extent, object);
	};
	projection.fitSize = function(size, object) {
		return fitSize(projection, size, object);
	};
	projection.fitWidth = function(width, object) {
		return fitWidth(projection, width, object);
	};
	projection.fitHeight = function(height, object) {
		return fitHeight(projection, height, object);
	};
	function recenter() {
		var center = scaleTranslateRotate(k, 0, 0, sx, sy, alpha).apply(null, project(lambda, phi)), transform = scaleTranslateRotate(k, x - center[0], y - center[1], sx, sy, alpha);
		rotate = rotateRadians(deltaLambda, deltaPhi, deltaGamma);
		projectTransform = compose_default(project, transform);
		projectRotateTransform = compose_default(rotate, projectTransform);
		projectResample = resample_default(projectTransform, delta2);
		return reset();
	}
	function reset() {
		cache = cacheStream = null;
		return projection;
	}
	return function() {
		project = projectAt.apply(this, arguments);
		projection.invert = project.invert && invert;
		return recenter();
	};
}
var transformRadians;
var init_projection = __esmMin((() => {
	init_antimeridian();
	init_circle();
	init_rectangle();
	init_compose();
	init_identity$1();
	init_math();
	init_rotation();
	init_transform();
	init_fit();
	init_resample();
	transformRadians = transformer({ point: function(x, y) {
		this.stream.point(x * radians, y * radians);
	} });
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/conic.js
function conicProjection(projectAt) {
	var phi0 = 0, phi1 = pi / 3, m = projectionMutator(projectAt), p = m(phi0, phi1);
	p.parallels = function(_) {
		return arguments.length ? m(phi0 = _[0] * radians, phi1 = _[1] * radians) : [phi0 * degrees, phi1 * degrees];
	};
	return p;
}
var init_conic = __esmMin((() => {
	init_math();
	init_projection();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/cylindricalEqualArea.js
function cylindricalEqualAreaRaw(phi0) {
	var cosPhi0 = cos(phi0);
	function forward(lambda, phi) {
		return [lambda * cosPhi0, sin(phi) / cosPhi0];
	}
	forward.invert = function(x, y) {
		return [x / cosPhi0, asin(y * cosPhi0)];
	};
	return forward;
}
var init_cylindricalEqualArea = __esmMin((() => {
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/conicEqualArea.js
function conicEqualAreaRaw(y0, y1) {
	var sy0 = sin(y0), n = (sy0 + sin(y1)) / 2;
	if (abs(n) < 1e-6) return cylindricalEqualAreaRaw(y0);
	var c = 1 + sy0 * (2 * n - sy0), r0 = sqrt(c) / n;
	function project(x, y) {
		var r = sqrt(c - 2 * n * sin(y)) / n;
		return [r * sin(x *= n), r0 - r * cos(x)];
	}
	project.invert = function(x, y) {
		var r0y = r0 - y, l = atan2(x, abs(r0y)) * sign(r0y);
		if (r0y * n < 0) l -= pi * sign(x) * sign(r0y);
		return [l / n, asin((c - (x * x + r0y * r0y) * n * n) / (2 * n))];
	};
	return project;
}
function conicEqualArea_default() {
	return conicProjection(conicEqualAreaRaw).scale(155.424).center([0, 33.6442]);
}
var init_conicEqualArea = __esmMin((() => {
	init_math();
	init_conic();
	init_cylindricalEqualArea();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/albers.js
function albers_default() {
	return conicEqualArea_default().parallels([29.5, 45.5]).scale(1070).translate([480, 250]).rotate([96, 0]).center([-.6, 38.7]);
}
var init_albers = __esmMin((() => {
	init_conicEqualArea();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/albersUsa.js
function multiplex(streams) {
	var n = streams.length;
	return {
		point: function(x, y) {
			var i = -1;
			while (++i < n) streams[i].point(x, y);
		},
		sphere: function() {
			var i = -1;
			while (++i < n) streams[i].sphere();
		},
		lineStart: function() {
			var i = -1;
			while (++i < n) streams[i].lineStart();
		},
		lineEnd: function() {
			var i = -1;
			while (++i < n) streams[i].lineEnd();
		},
		polygonStart: function() {
			var i = -1;
			while (++i < n) streams[i].polygonStart();
		},
		polygonEnd: function() {
			var i = -1;
			while (++i < n) streams[i].polygonEnd();
		}
	};
}
function albersUsa_default() {
	var cache, cacheStream, lower48 = albers_default(), lower48Point, alaska = conicEqualArea_default().rotate([154, 0]).center([-2, 58.5]).parallels([55, 65]), alaskaPoint, hawaii = conicEqualArea_default().rotate([157, 0]).center([-3, 19.9]).parallels([8, 18]), hawaiiPoint, point, pointStream = { point: function(x, y) {
		point = [x, y];
	} };
	function albersUsa(coordinates) {
		var x = coordinates[0], y = coordinates[1];
		return point = null, (lower48Point.point(x, y), point) || (alaskaPoint.point(x, y), point) || (hawaiiPoint.point(x, y), point);
	}
	albersUsa.invert = function(coordinates) {
		var k = lower48.scale(), t = lower48.translate(), x = (coordinates[0] - t[0]) / k, y = (coordinates[1] - t[1]) / k;
		return (y >= .12 && y < .234 && x >= -.425 && x < -.214 ? alaska : y >= .166 && y < .234 && x >= -.214 && x < -.115 ? hawaii : lower48).invert(coordinates);
	};
	albersUsa.stream = function(stream) {
		return cache && cacheStream === stream ? cache : cache = multiplex([
			lower48.stream(cacheStream = stream),
			alaska.stream(stream),
			hawaii.stream(stream)
		]);
	};
	albersUsa.precision = function(_) {
		if (!arguments.length) return lower48.precision();
		lower48.precision(_), alaska.precision(_), hawaii.precision(_);
		return reset();
	};
	albersUsa.scale = function(_) {
		if (!arguments.length) return lower48.scale();
		lower48.scale(_), alaska.scale(_ * .35), hawaii.scale(_);
		return albersUsa.translate(lower48.translate());
	};
	albersUsa.translate = function(_) {
		if (!arguments.length) return lower48.translate();
		var k = lower48.scale(), x = +_[0], y = +_[1];
		lower48Point = lower48.translate(_).clipExtent([[x - .455 * k, y - .238 * k], [x + .455 * k, y + .238 * k]]).stream(pointStream);
		alaskaPoint = alaska.translate([x - .307 * k, y + .201 * k]).clipExtent([[x - .425 * k + epsilon, y + .12 * k + epsilon], [x - .214 * k - epsilon, y + .234 * k - epsilon]]).stream(pointStream);
		hawaiiPoint = hawaii.translate([x - .205 * k, y + .212 * k]).clipExtent([[x - .214 * k + epsilon, y + .166 * k + epsilon], [x - .115 * k - epsilon, y + .234 * k - epsilon]]).stream(pointStream);
		return reset();
	};
	albersUsa.fitExtent = function(extent, object) {
		return fitExtent(albersUsa, extent, object);
	};
	albersUsa.fitSize = function(size, object) {
		return fitSize(albersUsa, size, object);
	};
	albersUsa.fitWidth = function(width, object) {
		return fitWidth(albersUsa, width, object);
	};
	albersUsa.fitHeight = function(height, object) {
		return fitHeight(albersUsa, height, object);
	};
	function reset() {
		cache = cacheStream = null;
		return albersUsa;
	}
	return albersUsa.scale(1070);
}
var init_albersUsa = __esmMin((() => {
	init_math();
	init_albers();
	init_conicEqualArea();
	init_fit();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/azimuthal.js
function azimuthalRaw(scale) {
	return function(x, y) {
		var cx = cos(x), cy = cos(y), k = scale(cx * cy);
		if (k === Infinity) return [2, 0];
		return [k * cy * sin(x), k * sin(y)];
	};
}
function azimuthalInvert(angle) {
	return function(x, y) {
		var z = sqrt(x * x + y * y), c = angle(z), sc = sin(c), cc = cos(c);
		return [atan2(x * sc, z * cc), asin(z && y * sc / z)];
	};
}
var init_azimuthal = __esmMin((() => {
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/azimuthalEqualArea.js
function azimuthalEqualArea_default() {
	return projection(azimuthalEqualAreaRaw).scale(124.75).clipAngle(179.999);
}
var azimuthalEqualAreaRaw;
var init_azimuthalEqualArea = __esmMin((() => {
	init_math();
	init_azimuthal();
	init_projection();
	azimuthalEqualAreaRaw = azimuthalRaw(function(cxcy) {
		return sqrt(2 / (1 + cxcy));
	});
	azimuthalEqualAreaRaw.invert = azimuthalInvert(function(z) {
		return 2 * asin(z / 2);
	});
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/azimuthalEquidistant.js
function azimuthalEquidistant_default() {
	return projection(azimuthalEquidistantRaw).scale(79.4188).clipAngle(179.999);
}
var azimuthalEquidistantRaw;
var init_azimuthalEquidistant = __esmMin((() => {
	init_math();
	init_azimuthal();
	init_projection();
	azimuthalEquidistantRaw = azimuthalRaw(function(c) {
		return (c = acos(c)) && c / sin(c);
	});
	azimuthalEquidistantRaw.invert = azimuthalInvert(function(z) {
		return z;
	});
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/mercator.js
function mercatorRaw(lambda, phi) {
	return [lambda, log(tan((halfPi + phi) / 2))];
}
function mercator_default() {
	return mercatorProjection(mercatorRaw).scale(961 / tau);
}
function mercatorProjection(project) {
	var m = projection(project), center = m.center, scale = m.scale, translate = m.translate, clipExtent = m.clipExtent, x0 = null, y0, x1, y1;
	m.scale = function(_) {
		return arguments.length ? (scale(_), reclip()) : scale();
	};
	m.translate = function(_) {
		return arguments.length ? (translate(_), reclip()) : translate();
	};
	m.center = function(_) {
		return arguments.length ? (center(_), reclip()) : center();
	};
	m.clipExtent = function(_) {
		return arguments.length ? (_ == null ? x0 = y0 = x1 = y1 = null : (x0 = +_[0][0], y0 = +_[0][1], x1 = +_[1][0], y1 = +_[1][1]), reclip()) : x0 == null ? null : [[x0, y0], [x1, y1]];
	};
	function reclip() {
		var k = pi * scale(), t = m(rotation_default(m.rotate()).invert([0, 0]));
		return clipExtent(x0 == null ? [[t[0] - k, t[1] - k], [t[0] + k, t[1] + k]] : project === mercatorRaw ? [[Math.max(t[0] - k, x0), y0], [Math.min(t[0] + k, x1), y1]] : [[x0, Math.max(t[1] - k, y0)], [x1, Math.min(t[1] + k, y1)]]);
	}
	return reclip();
}
var init_mercator = __esmMin((() => {
	init_math();
	init_rotation();
	init_projection();
	mercatorRaw.invert = function(x, y) {
		return [x, 2 * atan(exp(y)) - halfPi];
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/conicConformal.js
function tany(y) {
	return tan((halfPi + y) / 2);
}
function conicConformalRaw(y0, y1) {
	var cy0 = cos(y0), n = y0 === y1 ? sin(y0) : log(cy0 / cos(y1)) / log(tany(y1) / tany(y0)), f = cy0 * pow(tany(y0), n) / n;
	if (!n) return mercatorRaw;
	function project(x, y) {
		if (f > 0) {
			if (y < -halfPi + 1e-6) y = -halfPi + epsilon;
		} else if (y > halfPi - 1e-6) y = halfPi - epsilon;
		var r = f / pow(tany(y), n);
		return [r * sin(n * x), f - r * cos(n * x)];
	}
	project.invert = function(x, y) {
		var fy = f - y, r = sign(n) * sqrt(x * x + fy * fy), l = atan2(x, abs(fy)) * sign(fy);
		if (fy * n < 0) l -= pi * sign(x) * sign(fy);
		return [l / n, 2 * atan(pow(f / r, 1 / n)) - halfPi];
	};
	return project;
}
function conicConformal_default() {
	return conicProjection(conicConformalRaw).scale(109.5).parallels([30, 30]);
}
var init_conicConformal = __esmMin((() => {
	init_math();
	init_conic();
	init_mercator();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/equirectangular.js
function equirectangularRaw(lambda, phi) {
	return [lambda, phi];
}
function equirectangular_default() {
	return projection(equirectangularRaw).scale(152.63);
}
var init_equirectangular = __esmMin((() => {
	init_projection();
	equirectangularRaw.invert = equirectangularRaw;
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/conicEquidistant.js
function conicEquidistantRaw(y0, y1) {
	var cy0 = cos(y0), n = y0 === y1 ? sin(y0) : (cy0 - cos(y1)) / (y1 - y0), g = cy0 / n + y0;
	if (abs(n) < 1e-6) return equirectangularRaw;
	function project(x, y) {
		var gy = g - y, nx = n * x;
		return [gy * sin(nx), g - gy * cos(nx)];
	}
	project.invert = function(x, y) {
		var gy = g - y, l = atan2(x, abs(gy)) * sign(gy);
		if (gy * n < 0) l -= pi * sign(x) * sign(gy);
		return [l / n, g - sign(n) * sqrt(x * x + gy * gy)];
	};
	return project;
}
function conicEquidistant_default() {
	return conicProjection(conicEquidistantRaw).scale(131.154).center([0, 13.9389]);
}
var init_conicEquidistant = __esmMin((() => {
	init_math();
	init_conic();
	init_equirectangular();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/equalEarth.js
function equalEarthRaw(lambda, phi) {
	var l = asin(M * sin(phi)), l2 = l * l, l6 = l2 * l2 * l2;
	return [lambda * cos(l) / (M * (A1 + 3 * A2 * l2 + l6 * (7 * A3 + 9 * A4 * l2))), l * (A1 + A2 * l2 + l6 * (A3 + A4 * l2))];
}
function equalEarth_default() {
	return projection(equalEarthRaw).scale(177.158);
}
var A1, A2, A3, A4, M, iterations;
var init_equalEarth = __esmMin((() => {
	init_projection();
	init_math();
	A1 = 1.340264, A2 = -.081106, A3 = 893e-6, A4 = .003796, M = sqrt(3) / 2, iterations = 12;
	equalEarthRaw.invert = function(x, y) {
		var l = y, l2 = l * l, l6 = l2 * l2 * l2;
		for (var i = 0, delta, fy, fpy; i < iterations; ++i) {
			fy = l * (A1 + A2 * l2 + l6 * (A3 + A4 * l2)) - y;
			fpy = A1 + 3 * A2 * l2 + l6 * (7 * A3 + 9 * A4 * l2);
			l -= delta = fy / fpy, l2 = l * l, l6 = l2 * l2 * l2;
			if (abs(delta) < 1e-12) break;
		}
		return [M * x * (A1 + 3 * A2 * l2 + l6 * (7 * A3 + 9 * A4 * l2)) / cos(l), asin(sin(l) / M)];
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/gnomonic.js
function gnomonicRaw(x, y) {
	var cy = cos(y), k = cos(x) * cy;
	return [cy * sin(x) / k, sin(y) / k];
}
function gnomonic_default() {
	return projection(gnomonicRaw).scale(144.049).clipAngle(60);
}
var init_gnomonic = __esmMin((() => {
	init_math();
	init_azimuthal();
	init_projection();
	gnomonicRaw.invert = azimuthalInvert(atan);
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/identity.js
function identity_default() {
	var k = 1, tx = 0, ty = 0, sx = 1, sy = 1, alpha = 0, ca, sa, x0 = null, y0, x1, y1, kx = 1, ky = 1, transform = transformer({ point: function(x, y) {
		var p = projection([x, y]);
		this.stream.point(p[0], p[1]);
	} }), postclip = identity_default$1, cache, cacheStream;
	function reset() {
		kx = k * sx;
		ky = k * sy;
		cache = cacheStream = null;
		return projection;
	}
	function projection(p) {
		var x = p[0] * kx, y = p[1] * ky;
		if (alpha) {
			var t = y * ca - x * sa;
			x = x * ca + y * sa;
			y = t;
		}
		return [x + tx, y + ty];
	}
	projection.invert = function(p) {
		var x = p[0] - tx, y = p[1] - ty;
		if (alpha) {
			var t = y * ca + x * sa;
			x = x * ca - y * sa;
			y = t;
		}
		return [x / kx, y / ky];
	};
	projection.stream = function(stream) {
		return cache && cacheStream === stream ? cache : cache = transform(postclip(cacheStream = stream));
	};
	projection.postclip = function(_) {
		return arguments.length ? (postclip = _, x0 = y0 = x1 = y1 = null, reset()) : postclip;
	};
	projection.clipExtent = function(_) {
		return arguments.length ? (postclip = _ == null ? (x0 = y0 = x1 = y1 = null, identity_default$1) : clipRectangle(x0 = +_[0][0], y0 = +_[0][1], x1 = +_[1][0], y1 = +_[1][1]), reset()) : x0 == null ? null : [[x0, y0], [x1, y1]];
	};
	projection.scale = function(_) {
		return arguments.length ? (k = +_, reset()) : k;
	};
	projection.translate = function(_) {
		return arguments.length ? (tx = +_[0], ty = +_[1], reset()) : [tx, ty];
	};
	projection.angle = function(_) {
		return arguments.length ? (alpha = _ % 360 * radians, sa = sin(alpha), ca = cos(alpha), reset()) : alpha * degrees;
	};
	projection.reflectX = function(_) {
		return arguments.length ? (sx = _ ? -1 : 1, reset()) : sx < 0;
	};
	projection.reflectY = function(_) {
		return arguments.length ? (sy = _ ? -1 : 1, reset()) : sy < 0;
	};
	projection.fitExtent = function(extent, object) {
		return fitExtent(projection, extent, object);
	};
	projection.fitSize = function(size, object) {
		return fitSize(projection, size, object);
	};
	projection.fitWidth = function(width, object) {
		return fitWidth(projection, width, object);
	};
	projection.fitHeight = function(height, object) {
		return fitHeight(projection, height, object);
	};
	return projection;
}
var init_identity = __esmMin((() => {
	init_rectangle();
	init_identity$1();
	init_transform();
	init_fit();
	init_math();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/naturalEarth1.js
function naturalEarth1Raw(lambda, phi) {
	var phi2 = phi * phi, phi4 = phi2 * phi2;
	return [lambda * (.8707 - .131979 * phi2 + phi4 * (-.013791 + phi4 * (.003971 * phi2 - .001529 * phi4))), phi * (1.007226 + phi2 * (.015085 + phi4 * (-.044475 + .028874 * phi2 - .005916 * phi4)))];
}
function naturalEarth1_default() {
	return projection(naturalEarth1Raw).scale(175.295);
}
var init_naturalEarth1 = __esmMin((() => {
	init_projection();
	init_math();
	naturalEarth1Raw.invert = function(x, y) {
		var phi = y, i = 25, delta;
		do {
			var phi2 = phi * phi, phi4 = phi2 * phi2;
			phi -= delta = (phi * (1.007226 + phi2 * (.015085 + phi4 * (-.044475 + .028874 * phi2 - .005916 * phi4))) - y) / (1.007226 + phi2 * (.015085 * 3 + phi4 * (-.044475 * 7 + .028874 * 9 * phi2 - .005916 * 11 * phi4)));
		} while (abs(delta) > 1e-6 && --i > 0);
		return [x / (.8707 + (phi2 = phi * phi) * (-.131979 + phi2 * (-.013791 + phi2 * phi2 * phi2 * (.003971 - .001529 * phi2)))), phi];
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/orthographic.js
function orthographicRaw(x, y) {
	return [cos(y) * sin(x), sin(y)];
}
function orthographic_default() {
	return projection(orthographicRaw).scale(249.5).clipAngle(90 + epsilon);
}
var init_orthographic = __esmMin((() => {
	init_math();
	init_azimuthal();
	init_projection();
	orthographicRaw.invert = azimuthalInvert(asin);
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/stereographic.js
function stereographicRaw(x, y) {
	var cy = cos(y), k = 1 + cos(x) * cy;
	return [cy * sin(x) / k, sin(y) / k];
}
function stereographic_default() {
	return projection(stereographicRaw).scale(250).clipAngle(142);
}
var init_stereographic = __esmMin((() => {
	init_math();
	init_azimuthal();
	init_projection();
	stereographicRaw.invert = azimuthalInvert(function(z) {
		return 2 * atan(z);
	});
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/projection/transverseMercator.js
function transverseMercatorRaw(lambda, phi) {
	return [log(tan((halfPi + phi) / 2)), -lambda];
}
function transverseMercator_default() {
	var m = mercatorProjection(transverseMercatorRaw), center = m.center, rotate = m.rotate;
	m.center = function(_) {
		return arguments.length ? center([-_[1], _[0]]) : (_ = center(), [_[1], -_[0]]);
	};
	m.rotate = function(_) {
		return arguments.length ? rotate([
			_[0],
			_[1],
			_.length > 2 ? _[2] + 90 : 90
		]) : (_ = rotate(), [
			_[0],
			_[1],
			_[2] - 90
		]);
	};
	return rotate([
		0,
		0,
		90
	]).scale(159.155);
}
var init_transverseMercator = __esmMin((() => {
	init_math();
	init_mercator();
	transverseMercatorRaw.invert = function(x, y) {
		return [-y, 2 * atan(exp(x)) - halfPi];
	};
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-geo/src/index.js
var src_exports$1 = /* @__PURE__ */ __exportAll({
	geoAlbers: () => albers_default,
	geoAlbersUsa: () => albersUsa_default,
	geoArea: () => area_default,
	geoAzimuthalEqualArea: () => azimuthalEqualArea_default,
	geoAzimuthalEqualAreaRaw: () => azimuthalEqualAreaRaw,
	geoAzimuthalEquidistant: () => azimuthalEquidistant_default,
	geoAzimuthalEquidistantRaw: () => azimuthalEquidistantRaw,
	geoBounds: () => bounds_default,
	geoCentroid: () => centroid_default,
	geoCircle: () => circle_default$1,
	geoClipAntimeridian: () => antimeridian_default,
	geoClipCircle: () => circle_default,
	geoClipExtent: () => extent_default,
	geoClipRectangle: () => clipRectangle,
	geoConicConformal: () => conicConformal_default,
	geoConicConformalRaw: () => conicConformalRaw,
	geoConicEqualArea: () => conicEqualArea_default,
	geoConicEqualAreaRaw: () => conicEqualAreaRaw,
	geoConicEquidistant: () => conicEquidistant_default,
	geoConicEquidistantRaw: () => conicEquidistantRaw,
	geoContains: () => contains_default,
	geoDistance: () => distance_default,
	geoEqualEarth: () => equalEarth_default,
	geoEqualEarthRaw: () => equalEarthRaw,
	geoEquirectangular: () => equirectangular_default,
	geoEquirectangularRaw: () => equirectangularRaw,
	geoGnomonic: () => gnomonic_default,
	geoGnomonicRaw: () => gnomonicRaw,
	geoGraticule: () => graticule,
	geoGraticule10: () => graticule10,
	geoIdentity: () => identity_default,
	geoInterpolate: () => interpolate_default,
	geoLength: () => length_default,
	geoMercator: () => mercator_default,
	geoMercatorRaw: () => mercatorRaw,
	geoNaturalEarth1: () => naturalEarth1_default,
	geoNaturalEarth1Raw: () => naturalEarth1Raw,
	geoOrthographic: () => orthographic_default,
	geoOrthographicRaw: () => orthographicRaw,
	geoPath: () => path_default,
	geoProjection: () => projection,
	geoProjectionMutator: () => projectionMutator,
	geoRotation: () => rotation_default,
	geoStereographic: () => stereographic_default,
	geoStereographicRaw: () => stereographicRaw,
	geoStream: () => stream_default,
	geoTransform: () => transform_default,
	geoTransverseMercator: () => transverseMercator_default,
	geoTransverseMercatorRaw: () => transverseMercatorRaw
});
var init_src$1 = __esmMin((() => {
	init_area$1();
	init_bounds$1();
	init_centroid$1();
	init_circle$1();
	init_antimeridian();
	init_circle();
	init_extent();
	init_rectangle();
	init_contains();
	init_distance();
	init_graticule();
	init_interpolate();
	init_length();
	init_path();
	init_albers();
	init_albersUsa();
	init_azimuthalEqualArea();
	init_azimuthalEquidistant();
	init_conicConformal();
	init_conicEqualArea();
	init_conicEquidistant();
	init_equalEarth();
	init_equirectangular();
	init_gnomonic();
	init_identity();
	init_projection();
	init_mercator();
	init_naturalEarth1();
	init_orthographic();
	init_stereographic();
	init_transverseMercator();
	init_rotation();
	init_stream();
	init_transform();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/namespaces.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/namespace.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/creator.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selector.js
function none() {}
function selector_default(selector) {
	return selector == null ? none : function() {
		return this.querySelector(selector);
	};
}
var init_selector = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/select.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/array.js
function array_default(x) {
	return typeof x === "object" && "length" in x ? x : Array.from(x);
}
var init_array = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selectorAll.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/selectAll.js
function arrayAll(select) {
	return function() {
		var group = select.apply(this, arguments);
		return group == null ? [] : array_default(group);
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/matcher.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/selectChild.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/selectChildren.js
function children() {
	return this.children;
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/filter.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/sparse.js
function sparse_default(update) {
	return new Array(update.length);
}
var init_sparse = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/enter.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/constant.js
function constant_default(x) {
	return function() {
		return x;
	};
}
var init_constant = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/data.js
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
		var parent = parents[j], group = groups[j], groupLength = group.length, data = array_default(value.call(parent, parent && parent.__data__, j, parents)), dataLength = data.length, enterGroup = enter[j] = new Array(dataLength), updateGroup = update[j] = new Array(dataLength);
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
var init_data = __esmMin((() => {
	init_selection();
	init_enter();
	init_array();
	init_constant();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/exit.js
function exit_default() {
	return new Selection(this._exit || this._groups.map(sparse_default), this._parents);
}
var init_exit = __esmMin((() => {
	init_sparse();
	init_selection();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/join.js
function join_default(onenter, onupdate, onexit) {
	var enter = this.enter(), update = this, exit = this.exit();
	enter = typeof onenter === "function" ? onenter(enter) : enter.append(onenter + "");
	if (onupdate != null) update = onupdate(update);
	if (onexit == null) exit.remove();
	else onexit(exit);
	return enter && update ? enter.merge(update).order() : update;
}
var init_join = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/merge.js
function merge_default(selection) {
	if (!(selection instanceof Selection)) throw new Error("invalid merge");
	for (var groups0 = this._groups, groups1 = selection._groups, m0 = groups0.length, m1 = groups1.length, m = Math.min(m0, m1), merges = new Array(m0), j = 0; j < m; ++j) for (var group0 = groups0[j], group1 = groups1[j], n = group0.length, merge = merges[j] = new Array(n), node, i = 0; i < n; ++i) if (node = group0[i] || group1[i]) merge[i] = node;
	for (; j < m0; ++j) merges[j] = groups0[j];
	return new Selection(merges, this._parents);
}
var init_merge = __esmMin((() => {
	init_selection();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/order.js
function order_default() {
	for (var groups = this._groups, j = -1, m = groups.length; ++j < m;) for (var group = groups[j], i = group.length - 1, next = group[i], node; --i >= 0;) if (node = group[i]) {
		if (next && node.compareDocumentPosition(next) ^ 4) next.parentNode.insertBefore(node, next);
		next = node;
	}
	return this;
}
var init_order = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/sort.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/call.js
function call_default() {
	var callback = arguments[0];
	arguments[0] = this;
	callback.apply(null, arguments);
	return this;
}
var init_call = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/nodes.js
function nodes_default() {
	return Array.from(this);
}
var init_nodes = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/node.js
function node_default() {
	for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) for (var group = groups[j], i = 0, n = group.length; i < n; ++i) {
		var node = group[i];
		if (node) return node;
	}
	return null;
}
var init_node = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/size.js
function size_default() {
	let size = 0;
	for (const node of this) ++size;
	return size;
}
var init_size = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/empty.js
function empty_default() {
	return !this.node();
}
var init_empty = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/each.js
function each_default(callback) {
	for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) for (var group = groups[j], i = 0, n = group.length, node; i < n; ++i) if (node = group[i]) callback.call(node, node.__data__, i, group);
	return this;
}
var init_each = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/attr.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/window.js
function window_default(node) {
	return node.ownerDocument && node.ownerDocument.defaultView || node.document && node || node.defaultView;
}
var init_window = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/style.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/property.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/classed.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/text.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/html.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/raise.js
function raise() {
	if (this.nextSibling) this.parentNode.appendChild(this);
}
function raise_default() {
	return this.each(raise);
}
var init_raise = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/lower.js
function lower() {
	if (this.previousSibling) this.parentNode.insertBefore(this, this.parentNode.firstChild);
}
function lower_default() {
	return this.each(lower);
}
var init_lower = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/append.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/insert.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/remove.js
function remove() {
	var parent = this.parentNode;
	if (parent) parent.removeChild(this);
}
function remove_default() {
	return this.each(remove);
}
var init_remove = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/clone.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/datum.js
function datum_default(value) {
	return arguments.length ? this.property("__data__", value) : this.node().__data__;
}
var init_datum = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/on.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/dispatch.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/iterator.js
function* iterator_default() {
	for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) for (var group = groups[j], i = 0, n = group.length, node; i < n; ++i) if (node = group[i]) yield node;
}
var init_iterator = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selection/index.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/select.js
function select_default(selector) {
	return typeof selector === "string" ? new Selection([[document.querySelector(selector)]], [document.documentElement]) : new Selection([[selector]], root);
}
var init_select = __esmMin((() => {
	init_selection();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/create.js
function create_default(name) {
	return select_default(creator_default(name).call(document.documentElement));
}
var init_create = __esmMin((() => {
	init_creator();
	init_select();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/local.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/sourceEvent.js
function sourceEvent_default(event) {
	let sourceEvent;
	while (sourceEvent = event.sourceEvent) event = sourceEvent;
	return event;
}
var init_sourceEvent = __esmMin((() => {}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/pointer.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/pointers.js
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
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/selectAll.js
function selectAll_default(selector) {
	return typeof selector === "string" ? new Selection([document.querySelectorAll(selector)], [document.documentElement]) : new Selection([selector == null ? [] : array_default(selector)], root);
}
var init_selectAll = __esmMin((() => {
	init_array();
	init_selection();
}));
//#endregion
//#region node_modules/react-simple-maps/node_modules/d3-selection/src/index.js
var src_exports = /* @__PURE__ */ __exportAll({
	create: () => create_default,
	creator: () => creator_default,
	local: () => local,
	matcher: () => matcher_default,
	namespace: () => namespace_default,
	namespaces: () => namespaces_default,
	pointer: () => pointer_default,
	pointers: () => pointers_default,
	select: () => select_default,
	selectAll: () => selectAll_default,
	selection: () => selection,
	selector: () => selector_default,
	selectorAll: () => selectorAll_default,
	style: () => styleValue,
	window: () => window_default
});
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
//#region node_modules/react-simple-maps/dist/index.umd.js
var require_index_umd = /* @__PURE__ */ __commonJSMin(((exports, module) => {
	(function(e, t) {
		"object" == typeof exports && "undefined" != typeof module ? t(exports, require_react(), require_prop_types(), (init_src$1(), __toCommonJS(src_exports$1)), (init_src$3(), __toCommonJS(src_exports$2)), (init_src$4(), __toCommonJS(src_exports$3)), (init_src(), __toCommonJS(src_exports))) : "function" == typeof define && define.amd ? define([
			"exports",
			"react",
			"prop-types",
			"d3-geo",
			"topojson-client",
			"d3-zoom",
			"d3-selection"
		], t) : t((e = "undefined" != typeof globalThis ? globalThis : e || self).reactSimpleMaps = e.reactSimpleMaps || {}, e.React, e.PropTypes, e.d3, e.topojson, e.d3, e.d3);
	})(exports, (function(e, t, r, o, n, a, u) {
		"use strict";
		function s(e) {
			return e && "object" == typeof e && "default" in e ? e : { default: e };
		}
		function l(e) {
			if (e && e.__esModule) return e;
			var t = Object.create(null);
			return e && Object.keys(e).forEach((function(r) {
				if ("default" !== r) {
					var o = Object.getOwnPropertyDescriptor(e, r);
					Object.defineProperty(t, r, o.get ? o : {
						enumerable: !0,
						get: function() {
							return e[r];
						}
					});
				}
			})), t.default = e, Object.freeze(t);
		}
		var i = s(t), c = s(r), f = l(o);
		function d(e, t) {
			var r = Object.keys(e);
			if (Object.getOwnPropertySymbols) {
				var o = Object.getOwnPropertySymbols(e);
				t && (o = o.filter((function(t) {
					return Object.getOwnPropertyDescriptor(e, t).enumerable;
				}))), r.push.apply(r, o);
			}
			return r;
		}
		function p(e) {
			for (var t = 1; t < arguments.length; t++) {
				var r = null != arguments[t] ? arguments[t] : {};
				t % 2 ? d(Object(r), !0).forEach((function(t) {
					y(e, t, r[t]);
				})) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(r)) : d(Object(r)).forEach((function(t) {
					Object.defineProperty(e, t, Object.getOwnPropertyDescriptor(r, t));
				}));
			}
			return e;
		}
		function m(e) {
			return m = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(e) {
				return typeof e;
			} : function(e) {
				return e && "function" == typeof Symbol && e.constructor === Symbol && e !== Symbol.prototype ? "symbol" : typeof e;
			}, m(e);
		}
		function y(e, t, r) {
			return t in e ? Object.defineProperty(e, t, {
				value: r,
				enumerable: !0,
				configurable: !0,
				writable: !0
			}) : e[t] = r, e;
		}
		function g() {
			return g = Object.assign ? Object.assign.bind() : function(e) {
				for (var t = 1; t < arguments.length; t++) {
					var r = arguments[t];
					for (var o in r) Object.prototype.hasOwnProperty.call(r, o) && (e[o] = r[o]);
				}
				return e;
			}, g.apply(this, arguments);
		}
		function v(e, t) {
			if (null == e) return {};
			var r, o, n = function(e, t) {
				if (null == e) return {};
				var r, o, n = {}, a = Object.keys(e);
				for (o = 0; o < a.length; o++) r = a[o], t.indexOf(r) >= 0 || (n[r] = e[r]);
				return n;
			}(e, t);
			if (Object.getOwnPropertySymbols) {
				var a = Object.getOwnPropertySymbols(e);
				for (o = 0; o < a.length; o++) r = a[o], t.indexOf(r) >= 0 || Object.prototype.propertyIsEnumerable.call(e, r) && (n[r] = e[r]);
			}
			return n;
		}
		function h(e, t) {
			return function(e) {
				if (Array.isArray(e)) return e;
			}(e) || function(e, t) {
				var r = null == e ? null : "undefined" != typeof Symbol && e[Symbol.iterator] || e["@@iterator"];
				if (null == r) return;
				var o, n, a = [], u = !0, s = !1;
				try {
					for (r = r.call(e); !(u = (o = r.next()).done) && (a.push(o.value), !t || a.length !== t); u = !0);
				} catch (e) {
					s = !0, n = e;
				} finally {
					try {
						u || null == r.return || r.return();
					} finally {
						if (s) throw n;
					}
				}
				return a;
			}(e, t) || function(e, t) {
				if (!e) return;
				if ("string" == typeof e) return b(e, t);
				var r = Object.prototype.toString.call(e).slice(8, -1);
				"Object" === r && e.constructor && (r = e.constructor.name);
				if ("Map" === r || "Set" === r) return Array.from(e);
				if ("Arguments" === r || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(r)) return b(e, t);
			}(e, t) || function() {
				throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
			}();
		}
		function b(e, t) {
			(null == t || t > e.length) && (t = e.length);
			for (var r = 0, o = new Array(t); r < t; r++) o[r] = e[r];
			return o;
		}
		var j = [
			"width",
			"height",
			"projection",
			"projectionConfig"
		], M = f.geoPath, E = v(f, ["geoPath"]), x = t.createContext(), k = function(e) {
			var r = e.width, o = e.height, n = e.projection, a = e.projectionConfig, u = v(e, j), s = h(a.center || [], 2), l = s[0], c = s[1], f = h(a.rotate || [], 3), d = f[0], p = f[1], m = f[2], y = h(a.parallels || [], 2), b = y[0], k = y[1], w = a.scale || null, O = t.useMemo((function() {
				return function(e) {
					var t = e.projectionConfig, r = void 0 === t ? {} : t, o = e.projection, n = void 0 === o ? "geoEqualEarth" : o, a = e.width, u = void 0 === a ? 800 : a, s = e.height, l = void 0 === s ? 600 : s;
					if ("function" == typeof n) return n;
					var i = E[n]().translate([u / 2, l / 2]);
					return [
						i.center ? "center" : null,
						i.rotate ? "rotate" : null,
						i.scale ? "scale" : null,
						i.parallels ? "parallels" : null
					].forEach((function(e) {
						e && (i = i[e](r[e] || i[e]()));
					})), i;
				}({
					projectionConfig: {
						center: l || 0 === l || c || 0 === c ? [l, c] : null,
						rotate: d || 0 === d || p || 0 === p ? [
							d,
							p,
							m
						] : null,
						parallels: b || 0 === b || k || 0 === k ? [b, k] : null,
						scale: w
					},
					projection: n,
					width: r,
					height: o
				});
			}), [
				r,
				o,
				n,
				l,
				c,
				d,
				p,
				m,
				b,
				k,
				w
			]), N = t.useCallback(O, [O]), S = t.useMemo((function() {
				return {
					width: r,
					height: o,
					projection: N,
					path: M().projection(N)
				};
			}), [
				r,
				o,
				N
			]);
			return i.default.createElement(x.Provider, g({ value: S }, u));
		};
		k.propTypes = {
			width: c.default.number,
			height: c.default.number,
			projection: c.default.oneOfType([c.default.string, c.default.func]),
			projectionConfig: c.default.object
		};
		var w = [
			"width",
			"height",
			"projection",
			"projectionConfig",
			"className"
		], O = t.forwardRef((function(e, t) {
			var r = e.width, o = void 0 === r ? 800 : r, n = e.height, a = void 0 === n ? 600 : n, u = e.projection, s = void 0 === u ? "geoEqualEarth" : u, l = e.projectionConfig, c = void 0 === l ? {} : l, f = e.className, d = void 0 === f ? "" : f, p = v(e, w);
			return i.default.createElement(k, {
				width: o,
				height: a,
				projection: s,
				projectionConfig: c
			}, i.default.createElement("svg", g({
				ref: t,
				viewBox: "0 0 ".concat(o, " ").concat(a),
				className: "rsm-svg ".concat(d)
			}, p)));
		}));
		function N(e, t, r) {
			var o = (e * r.k - e) / 2, n = (t * r.k - t) / 2;
			return [e / 2 - (o + r.x) / r.k, t / 2 - (n + r.y) / r.k];
		}
		function S(e, t) {
			if (!("Topology" === e.type)) return t ? t(e.features || e) : e.features || e;
			var r = n.feature(e, e.objects[Object.keys(e.objects)[0]]).features;
			return t ? t(r) : r;
		}
		function P(e) {
			return "Topology" === e.type ? {
				outline: n.mesh(e, e.objects[Object.keys(e.objects)[0]], (function(e, t) {
					return e === t;
				})),
				borders: n.mesh(e, e.objects[Object.keys(e.objects)[0]], (function(e, t) {
					return e !== t;
				}))
			} : null;
		}
		function C(e, t) {
			return e ? e.map((function(e, r) {
				return p(p({}, e), {}, {
					rsmKey: "geo-".concat(r),
					svgPath: t(e)
				});
			})) : [];
		}
		function T(e) {
			var r = e.geography, o = e.parseGeographies, n = t.useContext(x).path, a = h(t.useState({}), 2), u = a[0], s = a[1];
			t.useEffect((function() {
				var e;
				"undefined" !== ("undefined" == typeof window ? "undefined" : m(window)) && r && ("string" == typeof r ? (e = r, fetch(e).then((function(e) {
					if (!e.ok) throw Error(e.statusText);
					return e.json();
				})).catch((function(e) {
					console.log("There was a problem when fetching the data: ", e);
				}))).then((function(e) {
					e && s({
						geographies: S(e, o),
						mesh: P(e)
					});
				})) : s({
					geographies: S(r, o),
					mesh: P(r)
				}));
			}), [r, o]);
			var l = t.useMemo((function() {
				var e = u.mesh || {}, t = function(e, t, r) {
					return e && t ? {
						outline: p(p({}, e), {}, {
							rsmKey: "outline",
							svgPath: r(e)
						}),
						borders: p(p({}, t), {}, {
							rsmKey: "borders",
							svgPath: r(t)
						})
					} : {};
				}(e.outline, e.borders, n);
				return {
					geographies: C(u.geographies, n),
					outline: t.outline,
					borders: t.borders
				};
			}), [u, n]);
			return {
				geographies: l.geographies,
				outline: l.outline,
				borders: l.borders
			};
		}
		O.displayName = "ComposableMap", O.propTypes = {
			width: c.default.number,
			height: c.default.number,
			projection: c.default.oneOfType([c.default.string, c.default.func]),
			projectionConfig: c.default.object,
			className: c.default.string
		};
		var R = [
			"geography",
			"children",
			"parseGeographies",
			"className"
		], Z = t.forwardRef((function(e, r) {
			var o = e.geography, n = e.children, a = e.parseGeographies, u = e.className, s = void 0 === u ? "" : u, l = v(e, R), c = t.useContext(x), f = c.path, d = c.projection, p = T({
				geography: o,
				parseGeographies: a
			}), m = p.geographies, y = p.outline, h = p.borders;
			return i.default.createElement("g", g({
				ref: r,
				className: "rsm-geographies ".concat(s)
			}, l), m && m.length > 0 && n({
				geographies: m,
				outline: y,
				borders: h,
				path: f,
				projection: d
			}));
		}));
		Z.displayName = "Geographies", Z.propTypes = {
			geography: c.default.oneOfType([
				c.default.string,
				c.default.object,
				c.default.array
			]),
			children: c.default.func,
			parseGeographies: c.default.func,
			className: c.default.string
		};
		var z = [
			"geography",
			"onMouseEnter",
			"onMouseLeave",
			"onMouseDown",
			"onMouseUp",
			"onFocus",
			"onBlur",
			"style",
			"className"
		], G = t.forwardRef((function(e, r) {
			var o = e.geography, n = e.onMouseEnter, a = e.onMouseLeave, u = e.onMouseDown, s = e.onMouseUp, l = e.onFocus, c = e.onBlur, f = e.style, d = void 0 === f ? {} : f, p = e.className, m = void 0 === p ? "" : p, y = v(e, z), b = h(t.useState(!1), 2), j = b[0], M = b[1], E = h(t.useState(!1), 2), x = E[0], k = E[1];
			return i.default.createElement("path", g({
				ref: r,
				tabIndex: "0",
				className: "rsm-geography ".concat(m),
				d: o.svgPath,
				onMouseEnter: function(e) {
					k(!0), n && n(e);
				},
				onMouseLeave: function(e) {
					k(!1), j && M(!1), a && a(e);
				},
				onFocus: function(e) {
					k(!0), l && l(e);
				},
				onBlur: function(e) {
					k(!1), j && M(!1), c && c(e);
				},
				onMouseDown: function(e) {
					M(!0), u && u(e);
				},
				onMouseUp: function(e) {
					M(!1), s && s(e);
				},
				style: d[j || x ? j ? "pressed" : "hover" : "default"]
			}, y));
		}));
		G.displayName = "Geography", G.propTypes = {
			geography: c.default.object,
			onMouseEnter: c.default.func,
			onMouseLeave: c.default.func,
			onMouseDown: c.default.func,
			onMouseUp: c.default.func,
			onFocus: c.default.func,
			onBlur: c.default.func,
			style: c.default.object,
			className: c.default.string
		};
		var D = t.memo(G), L = [
			"fill",
			"stroke",
			"step",
			"className"
		], A = t.forwardRef((function(e, r) {
			var n = e.fill, a = void 0 === n ? "transparent" : n, u = e.stroke, s = void 0 === u ? "currentcolor" : u, l = e.step, c = void 0 === l ? [10, 10] : l, f = e.className, d = void 0 === f ? "" : f, p = v(e, L), m = t.useContext(x).path;
			return i.default.createElement("path", g({
				ref: r,
				d: m(o.geoGraticule().step(c)()),
				fill: a,
				stroke: s,
				className: "rsm-graticule ".concat(d)
			}, p));
		}));
		A.displayName = "Graticule", A.propTypes = {
			fill: c.default.string,
			stroke: c.default.string,
			step: c.default.array,
			className: c.default.string
		};
		var B = t.memo(A), F = ["value"], U = t.createContext(), q = {
			x: 0,
			y: 0,
			k: 1,
			transformString: "translate(0 0) scale(1)"
		}, W = function(e) {
			var t = e.value, r = void 0 === t ? q : t, o = v(e, F);
			return i.default.createElement(U.Provider, g({ value: r }, o));
		};
		W.propTypes = {
			x: c.default.number,
			y: c.default.number,
			k: c.default.number,
			transformString: c.default.string
		};
		function I(e) {
			var r = e.center, o = e.filterZoomEvent, n = e.onMoveStart, s = e.onMoveEnd, l = e.onMove, i = e.translateExtent, c = void 0 === i ? [[-Infinity, -Infinity], [Infinity, Infinity]] : i, f = e.scaleExtent, d = void 0 === f ? [1, 8] : f, p = e.zoom, m = void 0 === p ? 1 : p, y = t.useContext(x), g = y.width, v = y.height, b = y.projection, j = h(r, 2), M = j[0], E = j[1], k = h(t.useState({
				x: 0,
				y: 0,
				k: 1
			}), 2), w = k[0], O = k[1], S = t.useRef({
				x: 0,
				y: 0,
				k: 1
			}), P = t.useRef(), C = t.useRef(), T = t.useRef(!1), R = h(c, 2), Z = R[0], z = R[1], G = h(Z, 2), D = G[0], L = G[1], A = h(z, 2), B = A[0], F = A[1], U = h(d, 2), q = U[0], W = U[1];
			return t.useEffect((function() {
				var e = u.select(P.current);
				var t = a.zoom().filter((function(e) {
					return o ? o(e) : !!e && !e.ctrlKey && !e.button;
				})).scaleExtent([q, W]).translateExtent([[D, L], [B, F]]).on("start", (function(e) {
					n && !T.current && n({
						coordinates: b.invert(N(g, v, e.transform)),
						zoom: e.transform.k
					}, e);
				})).on("zoom", (function(e) {
					if (!T.current) {
						var t = e.transform, r = e.sourceEvent;
						O({
							x: t.x,
							y: t.y,
							k: t.k,
							dragging: r
						}), l && l({
							x: t.x,
							y: t.y,
							zoom: t.k,
							dragging: r
						}, e);
					}
				})).on("end", (function(e) {
					if (T.current) T.current = !1;
					else {
						var t = h(b.invert(N(g, v, e.transform)), 2), r = t[0], o = t[1];
						S.current = {
							x: r,
							y: o,
							k: e.transform.k
						}, s && s({
							coordinates: [r, o],
							zoom: e.transform.k
						}, e);
					}
				}));
				C.current = t, e.call(t);
			}), [
				g,
				v,
				D,
				L,
				B,
				F,
				q,
				W,
				b,
				n,
				l,
				s,
				o
			]), t.useEffect((function() {
				if (M !== S.current.x || E !== S.current.y || m !== S.current.k) {
					var e = b([M, E]), t = e[0] * m, r = e[1] * m, o = u.select(P.current);
					T.current = !0, o.call(C.current.transform, a.zoomIdentity.translate(g / 2 - t, v / 2 - r).scale(m)), O({
						x: g / 2 - t,
						y: v / 2 - r,
						k: m
					}), S.current = {
						x: M,
						y: E,
						k: m
					};
				}
			}), [
				M,
				E,
				m,
				g,
				v,
				b
			]), {
				mapRef: P,
				position: w,
				transformString: "translate(".concat(w.x, " ").concat(w.y, ") scale(").concat(w.k, ")")
			};
		}
		var K = [
			"center",
			"zoom",
			"minZoom",
			"maxZoom",
			"translateExtent",
			"filterZoomEvent",
			"onMoveStart",
			"onMove",
			"onMoveEnd",
			"className"
		], _ = t.forwardRef((function(e, r) {
			var o = e.center, n = void 0 === o ? [0, 0] : o, a = e.zoom, u = void 0 === a ? 1 : a, s = e.minZoom, l = void 0 === s ? 1 : s, c = e.maxZoom, f = void 0 === c ? 8 : c, d = e.translateExtent, p = e.filterZoomEvent, m = e.onMoveStart, y = e.onMove, h = e.onMoveEnd, b = e.className, j = v(e, K), M = t.useContext(x), E = M.width, k = M.height, w = I({
				center: n,
				filterZoomEvent: p,
				onMoveStart: m,
				onMove: y,
				onMoveEnd: h,
				scaleExtent: [l, f],
				translateExtent: d,
				zoom: u
			}), O = w.mapRef, N = w.transformString, S = w.position;
			return i.default.createElement(W, { value: {
				x: S.x,
				y: S.y,
				k: S.k,
				transformString: N
			} }, i.default.createElement("g", { ref: O }, i.default.createElement("rect", {
				width: E,
				height: k,
				fill: "transparent"
			}), i.default.createElement("g", g({
				ref: r,
				transform: N,
				className: "rsm-zoomable-group ".concat(b)
			}, j))));
		}));
		_.displayName = "ZoomableGroup", _.propTypes = {
			center: c.default.array,
			zoom: c.default.number,
			minZoom: c.default.number,
			maxZoom: c.default.number,
			translateExtent: c.default.arrayOf(c.default.array),
			onMoveStart: c.default.func,
			onMove: c.default.func,
			onMoveEnd: c.default.func,
			className: c.default.string
		};
		var Q = [
			"id",
			"fill",
			"stroke",
			"strokeWidth",
			"className"
		], $ = t.forwardRef((function(e, r) {
			var o = e.id, n = void 0 === o ? "rsm-sphere" : o, a = e.fill, u = void 0 === a ? "transparent" : a, s = e.stroke, l = void 0 === s ? "currentcolor" : s, c = e.strokeWidth, f = void 0 === c ? .5 : c, d = e.className, p = void 0 === d ? "" : d, m = v(e, Q), y = t.useContext(x).path, h = t.useMemo((function() {
				return y({ type: "Sphere" });
			}), [y]);
			return i.default.createElement(t.Fragment, null, i.default.createElement("defs", null, i.default.createElement("clipPath", { id: n }, i.default.createElement("path", { d: h }))), i.default.createElement("path", g({
				ref: r,
				d: h,
				fill: u,
				stroke: l,
				strokeWidth: f,
				style: { pointerEvents: "none" },
				className: "rsm-sphere ".concat(p)
			}, m)));
		}));
		$.displayName = "Sphere", $.propTypes = {
			id: c.default.string,
			fill: c.default.string,
			stroke: c.default.string,
			strokeWidth: c.default.number,
			className: c.default.string
		};
		var H = t.memo($), J = [
			"coordinates",
			"children",
			"onMouseEnter",
			"onMouseLeave",
			"onMouseDown",
			"onMouseUp",
			"onFocus",
			"onBlur",
			"style",
			"className"
		], V = t.forwardRef((function(e, r) {
			var o = e.coordinates, n = e.children, a = e.onMouseEnter, u = e.onMouseLeave, s = e.onMouseDown, l = e.onMouseUp, c = e.onFocus, f = e.onBlur, d = e.style, p = void 0 === d ? {} : d, m = e.className, y = void 0 === m ? "" : m, b = v(e, J), j = t.useContext(x).projection, M = h(t.useState(!1), 2), E = M[0], k = M[1], w = h(t.useState(!1), 2), O = w[0], N = w[1], S = h(j(o), 2), P = S[0], C = S[1];
			return i.default.createElement("g", g({
				ref: r,
				transform: "translate(".concat(P, ", ").concat(C, ")"),
				className: "rsm-marker ".concat(y),
				onMouseEnter: function(e) {
					N(!0), a && a(e);
				},
				onMouseLeave: function(e) {
					N(!1), E && k(!1), u && u(e);
				},
				onFocus: function(e) {
					N(!0), c && c(e);
				},
				onBlur: function(e) {
					N(!1), E && k(!1), f && f(e);
				},
				onMouseDown: function(e) {
					k(!0), s && s(e);
				},
				onMouseUp: function(e) {
					k(!1), l && l(e);
				},
				style: p[E || O ? E ? "pressed" : "hover" : "default"]
			}, b), n);
		}));
		V.displayName = "Marker", V.propTypes = {
			coordinates: c.default.array,
			children: c.default.oneOfType([c.default.node, c.default.arrayOf(c.default.node)]),
			onMouseEnter: c.default.func,
			onMouseLeave: c.default.func,
			onMouseDown: c.default.func,
			onMouseUp: c.default.func,
			onFocus: c.default.func,
			onBlur: c.default.func,
			style: c.default.object,
			className: c.default.string
		};
		var X = [
			"from",
			"to",
			"coordinates",
			"stroke",
			"strokeWidth",
			"fill",
			"className"
		], Y = t.forwardRef((function(e, r) {
			var o = e.from, n = void 0 === o ? [0, 0] : o, a = e.to, u = void 0 === a ? [0, 0] : a, s = e.coordinates, l = e.stroke, c = void 0 === l ? "currentcolor" : l, f = e.strokeWidth, d = void 0 === f ? 3 : f, p = e.fill, m = void 0 === p ? "transparent" : p, y = e.className, h = void 0 === y ? "" : y, b = v(e, X), j = t.useContext(x).path, M = {
				type: "LineString",
				coordinates: s || [n, u]
			};
			return i.default.createElement("path", g({
				ref: r,
				d: j(M),
				className: "rsm-line ".concat(h),
				stroke: c,
				strokeWidth: d,
				fill: m
			}, b));
		}));
		Y.displayName = "Line", Y.propTypes = {
			from: c.default.array,
			to: c.default.array,
			coordinates: c.default.array,
			stroke: c.default.string,
			strokeWidth: c.default.number,
			fill: c.default.string,
			className: c.default.string
		};
		var ee = [
			"subject",
			"children",
			"connectorProps",
			"dx",
			"dy",
			"curve",
			"className"
		], te = t.forwardRef((function(e, r) {
			var o = e.subject, n = e.children, a = e.connectorProps, u = e.dx, s = void 0 === u ? 30 : u, l = e.dy, c = void 0 === l ? 30 : l, f = e.curve, d = void 0 === f ? 0 : f, p = e.className, m = void 0 === p ? "" : p, y = v(e, ee), b = h((0, t.useContext(x).projection)(o), 2), j = b[0], M = b[1], E = function() {
				var e = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : 30, t = arguments.length > 1 && void 0 !== arguments[1] ? arguments[1] : 30, r = arguments.length > 2 && void 0 !== arguments[2] ? arguments[2] : .5, o = Array.isArray(r) ? r : [r, r], n = e / 2 * o[0], a = t / 2 * o[1];
				return "M".concat(0, ",", 0, " Q", -e / 2 - n, ",").concat(-t / 2 + a, " ").concat(-e, ",").concat(-t);
			}(s, c, d);
			return i.default.createElement("g", g({
				ref: r,
				transform: "translate(".concat(j + s, ", ").concat(M + c, ")"),
				className: "rsm-annotation ".concat(m)
			}, y), i.default.createElement("path", g({
				d: E,
				fill: "transparent",
				stroke: "#000"
			}, a)), n);
		}));
		te.displayName = "Annotation", te.propTypes = {
			subject: c.default.array,
			children: c.default.oneOfType([c.default.node, c.default.arrayOf(c.default.node)]),
			dx: c.default.number,
			dy: c.default.number,
			curve: c.default.number,
			connectorProps: c.default.object,
			className: c.default.string
		}, e.Annotation = te, e.ComposableMap = O, e.Geographies = Z, e.Geography = D, e.Graticule = B, e.Line = Y, e.MapContext = x, e.MapProvider = k, e.Marker = V, e.Sphere = H, e.ZoomPanContext = U, e.ZoomPanProvider = W, e.ZoomableGroup = _, e.useGeographies = T, e.useMapContext = function() {
			return t.useContext(x);
		}, e.useZoomPan = I, e.useZoomPanContext = function() {
			return t.useContext(U);
		}, Object.defineProperty(e, "__esModule", { value: !0 });
	}));
}));
//#endregion
export default require_index_umd();

//# sourceMappingURL=react-simple-maps.js.map