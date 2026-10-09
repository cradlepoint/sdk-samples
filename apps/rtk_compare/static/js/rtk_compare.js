/* rtk_compare — live map and dashboard.
 *
 * The map is a canvas-rendered Web Mercator view so that metre-level
 * differences between the pre-correction and corrected tracks stay visible
 * at any zoom. An optional OpenStreetMap raster basemap is drawn underneath;
 * everything else (points, tracks, scale bar) is local and works offline.
 *
 * Pre-correction points and their track use one flat colour. Corrected points
 * use the fix-quality colour, and each corrected track segment is drawn in the
 * colour of the newer of its two endpoints.
 */
(function () {
    'use strict';

    // Compact history tuple layout — mirrors the H_* constants in rtk_compare.py.
    var I_SEQ = 0;
    var I_TS = 1;
    var I_PRE_LAT = 2;
    var I_PRE_LON = 3;
    var I_PRE_ALT = 4;
    var I_PRE_Q = 5;
    var I_POST_LAT = 6;
    var I_POST_LON = 7;
    var I_POST_ALT = 8;
    var I_POST_Q = 9;
    var I_DH = 10;
    var I_DV = 11;
    var I_HACC = 12;

    var TILE_SIZE = 256;
    var MAX_TILE_ZOOM = 19;
    var MIN_ZOOM = 2;
    var MAX_ZOOM = 23;
    var FIT_MAX_ZOOM = 21;
    var TILE_CACHE_LIMIT = 300;
    var POLL_MS = 1000;
    var SAMPLE_TABLE_ROWS = 200;
    var BANNER_DEBOUNCE_POLLS = 5;
    var FALLBACK_PRE_COLOR = '#94a3b8';
    var FALLBACK_QUALITY_COLOR = '#64748b';

    var state = {
        points: [],
        generation: 0,
        lastSeq: 0,
        legend: null,
        qualityColors: {},
        qualityLabels: {},
        qualityAccuracy: {},
        preColor: FALLBACK_PRE_COLOR,
        latest: null,
        stats: null,
        info: null,
        center: null,          // {lat, lon}
        zoom: 19,
        follow: true,
        selected: null,
        layers: {
            post: true,
            postTrack: true,
            pre: true,
            preTrack: true,
            basemap: true
        },
        tiles: {},
        tileOrder: [],
        drag: null,
        needsDraw: false,
        polling: false,
        bannerShown: '',
        bannerPending: '',
        bannerPendingCount: 0,
        observedQualities: {}
    };

    var canvas = null;
    var ctx = null;

    // ---------------------------------------------------------------- utils

    function byId(id) {
        return document.getElementById(id);
    }

    function escapeHtml(value) {
        if (value === null || value === undefined) { return ''; }
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function isNum(value) {
        return typeof value === 'number' && isFinite(value);
    }

    function fmt(value, digits, suffix) {
        if (!isNum(value)) { return '\u2014'; }
        return value.toFixed(digits === undefined ? 2 : digits) + (suffix || '');
    }

    /* Format a distance in metres, switching to centimetres below 1 m.
     * RTK offsets and accuracies routinely land in the 1-30 cm range, where
     * "0.17 m" reads worse than "17 cm". metreDigits is the precision the
     * server actually sent, and the cm form drops two decimals to match it
     * exactly, so the conversion never invents or loses a digit. */
    function fmtMeters(value, metreDigits) {
        if (!isNum(value)) { return '\u2014'; }
        var digits = metreDigits === undefined ? 3 : metreDigits;
        if (Math.abs(value) < 1) {
            return (value * 100).toFixed(Math.max(0, digits - 2)) + ' cm';
        }
        return value.toFixed(digits) + ' m';
    }

    /* Two distances sharing one unit label, e.g. "17 / 14 cm". Falls back to
     * per-value units when one is sub-metre and the other is not. */
    function fmtMetersPair(first, second, metreDigits) {
        if (!isNum(first) && !isNum(second)) { return '\u2014'; }
        var digits = metreDigits === undefined ? 3 : metreDigits;
        var smallFirst = isNum(first) && Math.abs(first) < 1;
        var smallSecond = isNum(second) && Math.abs(second) < 1;
        var bothKnown = isNum(first) && isNum(second);
        if (bothKnown && smallFirst === smallSecond) {
            var scale = smallFirst ? 100 : 1;
            var places = smallFirst ? Math.max(0, digits - 2) : digits;
            return (first * scale).toFixed(places) + ' / ' +
                (second * scale).toFixed(places) +
                (smallFirst ? ' cm' : ' m');
        }
        return fmtMeters(first, digits) + ' / ' + fmtMeters(second, digits);
    }

    function fmtInt(value, suffix) {
        if (!isNum(value)) { return '\u2014'; }
        return String(Math.round(value)) + (suffix || '');
    }

    function fmtBytes(value) {
        if (!isNum(value)) { return '\u2014'; }
        var units = ['B', 'KB', 'MB', 'GB'];
        var index = 0;
        var size = value;
        while (size >= 1024 && index < units.length - 1) {
            size = size / 1024;
            index += 1;
        }
        return (index === 0 ? size.toFixed(0) : size.toFixed(1)) + ' ' + units[index];
    }

    function fmtDuration(seconds) {
        if (!isNum(seconds)) { return '\u2014'; }
        var total = Math.max(0, Math.round(seconds));
        var hours = Math.floor(total / 3600);
        var minutes = Math.floor((total % 3600) / 60);
        var secs = total % 60;
        if (hours) { return hours + 'h ' + minutes + 'm ' + secs + 's'; }
        if (minutes) { return minutes + 'm ' + secs + 's'; }
        return secs + 's';
    }

    function qualityColor(quality) {
        if (quality === null || quality === undefined) { return FALLBACK_QUALITY_COLOR; }
        return state.qualityColors[String(quality)] || FALLBACK_QUALITY_COLOR;
    }

    function qualityLabel(quality) {
        if (quality === null || quality === undefined) { return 'No data'; }
        return state.qualityLabels[String(quality)] || ('Quality ' + quality);
    }

    /* Pick black or white badge text for a background colour, using WCAG
     * relative luminance. Needed because the quality palette spans yellow and
     * orange, where fixed white text drops to ~2:1 contrast and is unreadable;
     * 0.179 is the luminance at which black overtakes white. */
    function contrastText(hex) {
        var match = /^#?([0-9a-f]{6})$/i.exec(String(hex || ''));
        if (!match) { return '#ffffff'; }
        var value = parseInt(match[1], 16);
        var channels = [(value >> 16) & 255, (value >> 8) & 255, value & 255];
        var linear = channels.map(function (raw) {
            var channel = raw / 255;
            return channel <= 0.03928
                ? channel / 12.92
                : Math.pow((channel + 0.055) / 1.055, 2.4);
        });
        var luminance = 0.2126 * linear[0] + 0.7152 * linear[1] +
            0.0722 * linear[2];
        return luminance > 0.179 ? '#1f2937' : '#ffffff';
    }

    /* Pre-correction readouts use the legend's grey square, not a
     * quality-coloured badge. Pre points are plotted in one flat colour
     * whatever their GGA quality, so colouring the label by quality would
     * imply map colours that do not exist. */
    function preQualityTag(label) {
        return '<span class="rtk-pre-tag">' +
            '<span class="rtk-legend-dot rtk-legend-pre" style="background:' +
            state.preColor + '"></span>' +
            escapeHtml(label || '\u2014') + '</span>';
    }

    function qualityBadge(quality, label) {
        var color = qualityColor(quality);
        return '<span class="rtk-badge" style="background:' + color +
            ';color:' + contrastText(color) + '">' +
            escapeHtml(label === undefined ? qualityLabel(quality) : label) +
            '</span>';
    }

    function qualityAccuracy(quality) {
        if (quality === null || quality === undefined) { return ''; }
        return state.qualityAccuracy[String(quality)] || '';
    }

    function kvRows(rows) {
        var html = '';
        var found = false;
        rows.forEach(function (row) {
            if (!row) { return; }
            found = true;
            var value = row.html !== undefined
                ? row.html
                : '<strong>' + escapeHtml(row.value) + '</strong>';
            html += '<div class="rtk-kv-row"><span>' + escapeHtml(row.label) +
                '</span>' + value + '</div>';
        });
        if (!found) { return '<p class="rtk-empty">No data.</p>'; }
        return html;
    }

    // ----------------------------------------------------------- projection

    function worldSize(zoom) {
        return TILE_SIZE * Math.pow(2, zoom);
    }

    function lonToWorldX(lon, zoom) {
        return (lon + 180) / 360 * worldSize(zoom);
    }

    function latToWorldY(lat, zoom) {
        var clamped = Math.max(-85.05112878, Math.min(85.05112878, lat));
        var sin = Math.sin(clamped * Math.PI / 180);
        return (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * worldSize(zoom);
    }

    function worldXToLon(x, zoom) {
        return x / worldSize(zoom) * 360 - 180;
    }

    function worldYToLat(y, zoom) {
        var n = Math.PI - 2 * Math.PI * y / worldSize(zoom);
        return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
    }

    function metersPerPixel(lat, zoom) {
        return 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, zoom);
    }

    // ------------------------------------------------------------ map model

    function canvasSize() {
        if (!canvas) { return { width: 0, height: 0 }; }
        return { width: canvas.clientWidth, height: canvas.clientHeight };
    }

    function ensureCenter() {
        if (state.center) { return; }
        var fix = latestFix();
        if (fix) {
            state.center = { lat: fix.lat, lon: fix.lon };
        }
    }

    function latestFix() {
        for (var i = state.points.length - 1; i >= 0; i -= 1) {
            var point = state.points[i];
            if (isNum(point[I_POST_LAT]) && isNum(point[I_POST_LON])) {
                return { lat: point[I_POST_LAT], lon: point[I_POST_LON] };
            }
            if (isNum(point[I_PRE_LAT]) && isNum(point[I_PRE_LON])) {
                return { lat: point[I_PRE_LAT], lon: point[I_PRE_LON] };
            }
        }
        var latest = state.latest;
        if (latest && latest.post && isNum(latest.post.lat)) {
            return { lat: latest.post.lat, lon: latest.post.lon };
        }
        if (latest && latest.pre && isNum(latest.pre.lat)) {
            return { lat: latest.pre.lat, lon: latest.pre.lon };
        }
        return null;
    }

    function toScreen(lat, lon, size) {
        var centerX = lonToWorldX(state.center.lon, state.zoom);
        var centerY = latToWorldY(state.center.lat, state.zoom);
        return {
            x: lonToWorldX(lon, state.zoom) - centerX + size.width / 2,
            y: latToWorldY(lat, state.zoom) - centerY + size.height / 2
        };
    }

    function fromScreen(x, y, size) {
        var centerX = lonToWorldX(state.center.lon, state.zoom);
        var centerY = latToWorldY(state.center.lat, state.zoom);
        return {
            lat: worldYToLat(centerY + y - size.height / 2, state.zoom),
            lon: worldXToLon(centerX + x - size.width / 2, state.zoom)
        };
    }

    function visibleCoordinates() {
        var coords = [];
        state.points.forEach(function (point) {
            if (state.layers.post && isNum(point[I_POST_LAT]) && isNum(point[I_POST_LON])) {
                coords.push([point[I_POST_LAT], point[I_POST_LON]]);
            }
            if (state.layers.pre && isNum(point[I_PRE_LAT]) && isNum(point[I_PRE_LON])) {
                coords.push([point[I_PRE_LAT], point[I_PRE_LON]]);
            }
        });
        return coords;
    }

    function fitAll() {
        var coords = visibleCoordinates();
        if (!coords.length) { return; }
        var minLat = coords[0][0];
        var maxLat = coords[0][0];
        var minLon = coords[0][1];
        var maxLon = coords[0][1];
        coords.forEach(function (coord) {
            minLat = Math.min(minLat, coord[0]);
            maxLat = Math.max(maxLat, coord[0]);
            minLon = Math.min(minLon, coord[1]);
            maxLon = Math.max(maxLon, coord[1]);
        });
        state.center = { lat: (minLat + maxLat) / 2, lon: (minLon + maxLon) / 2 };

        var size = canvasSize();
        var padding = 60;
        var usableWidth = Math.max(32, size.width - padding);
        var usableHeight = Math.max(32, size.height - padding);
        var zoom = MAX_ZOOM;
        for (var test = MAX_ZOOM; test >= MIN_ZOOM; test -= 0.25) {
            var spanX = Math.abs(lonToWorldX(maxLon, test) - lonToWorldX(minLon, test));
            var spanY = Math.abs(latToWorldY(minLat, test) - latToWorldY(maxLat, test));
            if (spanX <= usableWidth && spanY <= usableHeight) {
                zoom = test;
                break;
            }
            zoom = test;
        }
        // Cap the fitted zoom: a stationary receiver has a near-zero span and
        // would otherwise fit at max zoom, where the basemap is unusable.
        state.zoom = Math.max(MIN_ZOOM, Math.min(FIT_MAX_ZOOM, zoom));
        state.follow = false;
        syncFollowButton();
        requestDraw();
    }

    function setZoom(zoom, anchor) {
        var size = canvasSize();
        var clamped = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));
        if (!state.center) { return; }
        if (anchor) {
            var before = fromScreen(anchor.x, anchor.y, size);
            state.zoom = clamped;
            var after = fromScreen(anchor.x, anchor.y, size);
            state.center = {
                lat: state.center.lat + (before.lat - after.lat),
                lon: state.center.lon + (before.lon - after.lon)
              };
        } else {
            state.zoom = clamped;
        }
        requestDraw();
    }

    // ---------------------------------------------------------------- tiles

    function tileUrl(z, x, y) {
        return 'https://tile.openstreetmap.org/' + z + '/' + x + '/' + y + '.png';
    }

    function getTile(z, x, y) {
        var key = z + '/' + x + '/' + y;
        var entry = state.tiles[key];
        if (entry) { return entry; }

        var image = new Image();
        entry = { image: image, ready: false, failed: false };
        state.tiles[key] = entry;
        state.tileOrder.push(key);
        while (state.tileOrder.length > TILE_CACHE_LIMIT) {
            delete state.tiles[state.tileOrder.shift()];
        }
        image.onload = function () {
            entry.ready = true;
            requestDraw();
        };
        image.onerror = function () {
            entry.failed = true;
        };
        image.src = tileUrl(z, x, y);
        return entry;
    }

    function drawTiles(size) {
        var tileZoom = Math.max(0, Math.min(MAX_TILE_ZOOM, Math.round(state.zoom)));
        var scale = Math.pow(2, state.zoom - tileZoom);
        var drawn = TILE_SIZE * scale;
        var centerX = lonToWorldX(state.center.lon, tileZoom) * scale;
        var centerY = latToWorldY(state.center.lat, tileZoom) * scale;
        var originX = centerX - size.width / 2;
        var originY = centerY - size.height / 2;
        var count = Math.pow(2, tileZoom);

        var firstX = Math.floor(originX / drawn);
        var lastX = Math.floor((originX + size.width) / drawn);
        var firstY = Math.floor(originY / drawn);
        var lastY = Math.floor((originY + size.height) / drawn);

        for (var tx = firstX; tx <= lastX; tx += 1) {
            for (var ty = firstY; ty <= lastY; ty += 1) {
                if (ty < 0 || ty >= count) { continue; }
                var wrapped = ((tx % count) + count) % count;
                var tile = getTile(tileZoom, wrapped, ty);
                if (!tile.ready) { continue; }
                try {
                    ctx.drawImage(tile.image,
                        Math.round(tx * drawn - originX),
                        Math.round(ty * drawn - originY),
                        Math.ceil(drawn), Math.ceil(drawn));
                } catch (error) {
                    tile.failed = true;
                }
            }
        }
    }

    function drawGrid(size) {
        var step = 48;
        ctx.save();
        ctx.strokeStyle = 'rgba(128, 138, 157, 0.18)';
        ctx.lineWidth = 1;
        for (var x = 0; x <= size.width; x += step) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, size.height);
            ctx.stroke();
        }
        for (var y = 0; y <= size.height; y += step) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(size.width, y);
            ctx.stroke();
        }
        ctx.restore();
    }

    // ----------------------------------------------------------------- draw

    function requestDraw() {
        if (state.needsDraw) { return; }
        state.needsDraw = true;
        window.requestAnimationFrame(function () {
            state.needsDraw = false;
            draw();
        });
    }

    function draw() {
        if (!canvas || !ctx) { return; }
        var ratio = window.devicePixelRatio || 1;
        var size = canvasSize();
        if (!size.width || !size.height) { return; }

        if (canvas.width !== Math.round(size.width * ratio) ||
                canvas.height !== Math.round(size.height * ratio)) {
            canvas.width = Math.round(size.width * ratio);
            canvas.height = Math.round(size.height * ratio);
        }
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, size.width, size.height);

        ensureCenter();
        if (!state.center) {
            drawGrid(size);
            drawPlaceholder(size, 'Waiting for the first GNSS fix\u2026');
            updateScaleBar(null);
            return;
        }

        if (state.layers.basemap) {
            drawTiles(size);
        } else {
            drawGrid(size);
        }

        var preTrack = [];
        var postTrack = [];
        state.points.forEach(function (point) {
            if (isNum(point[I_PRE_LAT]) && isNum(point[I_PRE_LON])) {
                preTrack.push({
                    point: point,
                    screen: toScreen(point[I_PRE_LAT], point[I_PRE_LON], size)
                });
            }
            if (isNum(point[I_POST_LAT]) && isNum(point[I_POST_LON])) {
                postTrack.push({
                    point: point,
                    screen: toScreen(point[I_POST_LAT], point[I_POST_LON], size),
                    quality: point[I_POST_Q]
                });
            }
        });

        if (state.layers.preTrack) { drawFlatTrack(preTrack, state.preColor); }
        if (state.layers.postTrack) { drawQualityTrack(postTrack); }
        drawOffsetLink(size);
        if (state.layers.pre) { drawPrePoints(preTrack); }
        if (state.layers.post) { drawPostPoints(postTrack); }
        drawSelection(size);

        if (!state.points.length) {
            drawPlaceholder(size, 'No samples recorded yet.');
        }
        updateScaleBar(size);
        updateReadout();
    }

    function drawPlaceholder(size, message) {
        ctx.save();
        ctx.fillStyle = 'rgba(120, 130, 150, 0.9)';
        ctx.font = '13px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(message, size.width / 2, size.height / 2);
        ctx.restore();
    }

    function drawFlatTrack(items, color) {
        if (items.length < 2) { return; }
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.globalAlpha = 0.85;
        ctx.beginPath();
        items.forEach(function (item, index) {
            if (index === 0) {
                ctx.moveTo(item.screen.x, item.screen.y);
            } else {
                ctx.lineTo(item.screen.x, item.screen.y);
            }
        });
        ctx.stroke();
        ctx.restore();
    }

    function drawQualityTrack(items) {
        if (items.length < 2) { return; }
        ctx.save();
        ctx.lineWidth = 2.5;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.globalAlpha = 0.9;

        // Each segment takes the colour of its newer endpoint, so the track
        // changes colour wherever the fix quality changed.
        var index = 1;
        while (index < items.length) {
            var color = qualityColor(items[index].quality);
            ctx.strokeStyle = color;
            ctx.beginPath();
            ctx.moveTo(items[index - 1].screen.x, items[index - 1].screen.y);
            ctx.lineTo(items[index].screen.x, items[index].screen.y);
            var next = index + 1;
            while (next < items.length && qualityColor(items[next].quality) === color) {
                ctx.lineTo(items[next].screen.x, items[next].screen.y);
                next += 1;
            }
            ctx.stroke();
            index = next;
        }
        ctx.restore();
    }

    function drawPrePoints(items) {
        if (!items.length) { return; }
        ctx.save();
        ctx.fillStyle = state.preColor;
        ctx.strokeStyle = 'rgba(30, 41, 59, 0.55)';
        ctx.lineWidth = 1;
        items.forEach(function (item, index) {
            var radius = index === items.length - 1 ? 4.5 : 3;
            ctx.beginPath();
            ctx.arc(item.screen.x, item.screen.y, radius, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        });
        ctx.restore();
    }

    function drawPostPoints(items) {
        if (!items.length) { return; }
        ctx.save();
        // Dark outline, not white: the palette now includes yellow and orange,
        // which a white ring barely separates from a light basemap.
        ctx.strokeStyle = 'rgba(17, 24, 39, 0.7)';
        ctx.lineWidth = 1.2;
        items.forEach(function (item, index) {
            var isLatest = index === items.length - 1;
            ctx.fillStyle = qualityColor(item.quality);
            ctx.beginPath();
            ctx.arc(item.screen.x, item.screen.y, isLatest ? 6 : 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            if (isLatest) {
                ctx.save();
                ctx.strokeStyle = qualityColor(item.quality);
                ctx.lineWidth = 2;
                ctx.globalAlpha = 0.5;
                ctx.beginPath();
                ctx.arc(item.screen.x, item.screen.y, 11, 0, Math.PI * 2);
                ctx.stroke();
                ctx.restore();
            }
        });
        ctx.restore();
    }

    function drawOffsetLink(size) {
        if (!state.points.length) { return; }
        if (!state.layers.pre || !state.layers.post) { return; }
        var point = state.points[state.points.length - 1];
        if (!isNum(point[I_PRE_LAT]) || !isNum(point[I_POST_LAT])) { return; }
        var from = toScreen(point[I_PRE_LAT], point[I_PRE_LON], size);
        var to = toScreen(point[I_POST_LAT], point[I_POST_LON], size);
        ctx.save();
        ctx.strokeStyle = 'rgba(100, 116, 139, 0.9)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();
        ctx.restore();
    }

    function drawSelection(size) {
        var selected = state.selected;
        if (!selected) { return; }
        var lat = selected.kind === 'pre' ? selected.point[I_PRE_LAT] : selected.point[I_POST_LAT];
        var lon = selected.kind === 'pre' ? selected.point[I_PRE_LON] : selected.point[I_POST_LON];
        if (!isNum(lat) || !isNum(lon)) { return; }
        var screen = toScreen(lat, lon, size);
        ctx.save();
        ctx.strokeStyle = '#111827';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, 13, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
    }

    function updateScaleBar(size) {
        var textEl = byId('map-scale-text');
        var barEl = byId('map-scale-bar');
        if (!textEl || !barEl) { return; }
        if (!size || !state.center) {
            textEl.textContent = '\u2014';
            return;
        }
        var mpp = metersPerPixel(state.center.lat, state.zoom);
        var targetPixels = 90;
        var raw = mpp * targetPixels;
        var steps = [0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50,
                     100, 200, 500, 1000, 2000, 5000];
        var chosen = steps[0];
        for (var i = 0; i < steps.length; i += 1) {
            if (steps[i] <= raw) { chosen = steps[i]; }
        }
        barEl.style.width = Math.round(chosen / mpp) + 'px';
        if (chosen >= 1000) {
            textEl.textContent = (chosen / 1000) + ' km';
        } else if (chosen < 1) {
            textEl.textContent = Math.round(chosen * 100) + ' cm';
        } else {
            textEl.textContent = chosen + ' m';
        }
    }

    function updateReadout() {
        var el = byId('map-readout');
        if (!el) { return; }
        if (!state.center) {
            el.textContent = '\u2014';
            return;
        }
        el.textContent = state.center.lat.toFixed(7) + ', ' +
            state.center.lon.toFixed(7) + '  z' + state.zoom.toFixed(1);
    }

    // ---------------------------------------------------------- interaction

    function nearestPoint(x, y, size) {
        var best = null;
        var bestDistance = 18;
        state.points.forEach(function (point) {
            if (state.layers.post && isNum(point[I_POST_LAT])) {
                var post = toScreen(point[I_POST_LAT], point[I_POST_LON], size);
                var dPost = Math.hypot(post.x - x, post.y - y);
                if (dPost < bestDistance) {
                    bestDistance = dPost;
                    best = { point: point, kind: 'post' };
                }
            }
            if (state.layers.pre && isNum(point[I_PRE_LAT])) {
                var pre = toScreen(point[I_PRE_LAT], point[I_PRE_LON], size);
                var dPre = Math.hypot(pre.x - x, pre.y - y);
                if (dPre < bestDistance) {
                    bestDistance = dPre;
                    best = { point: point, kind: 'pre' };
                }
            }
        });
        return best;
    }

    function bindMapEvents() {
        canvas.addEventListener('wheel', function (event) {
            event.preventDefault();
            if (!state.center) { return; }
            var rect = canvas.getBoundingClientRect();
            var anchor = {
                x: event.clientX - rect.left,
                y: event.clientY - rect.top
            };
            var delta = event.deltaY < 0 ? 0.5 : -0.5;
            state.follow = false;
            syncFollowButton();
            setZoom(state.zoom + delta, anchor);
        }, { passive: false });

        canvas.addEventListener('pointerdown', function (event) {
            if (!state.center) { return; }
            canvas.setPointerCapture(event.pointerId);
            var rect = canvas.getBoundingClientRect();
            state.drag = {
                startX: event.clientX,
                startY: event.clientY,
                x: event.clientX - rect.left,
                y: event.clientY - rect.top,
                center: { lat: state.center.lat, lon: state.center.lon },
                moved: false
            };
        });

        canvas.addEventListener('pointermove', function (event) {
            if (!state.drag || !state.center) { return; }
            var dx = event.clientX - state.drag.startX;
            var dy = event.clientY - state.drag.startY;
            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                state.drag.moved = true;
                canvas.classList.add('rtk-dragging');
                state.follow = false;
                syncFollowButton();
            }
            if (!state.drag.moved) { return; }
            var centerX = lonToWorldX(state.drag.center.lon, state.zoom) - dx;
            var centerY = latToWorldY(state.drag.center.lat, state.zoom) - dy;
            state.center = {
                lat: worldYToLat(centerY, state.zoom),
                lon: worldXToLon(centerX, state.zoom)
            };
            requestDraw();
        });

        function endDrag(event) {
            if (!state.drag) { return; }
            var moved = state.drag.moved;
            var rect = canvas.getBoundingClientRect();
            var x = event.clientX - rect.left;
            var y = event.clientY - rect.top;
            state.drag = null;
            canvas.classList.remove('rtk-dragging');
            if (!moved) {
                state.selected = nearestPoint(x, y, canvasSize());
                renderSelected();
                requestDraw();
            }
        }

        canvas.addEventListener('pointerup', endDrag);
        canvas.addEventListener('pointercancel', function () {
            state.drag = null;
            canvas.classList.remove('rtk-dragging');
        });

        canvas.addEventListener('dblclick', function (event) {
            var rect = canvas.getBoundingClientRect();
            state.follow = false;
            syncFollowButton();
            setZoom(state.zoom + 1, {
                x: event.clientX - rect.left,
                y: event.clientY - rect.top
            });
        });

        window.addEventListener('resize', requestDraw);
    }

    function syncFollowButton() {
        var button = byId('map-follow');
        if (!button) { return; }
        button.classList.toggle('rtk-toggle-on', state.follow);
    }

    function bindControls() {
        var layerMap = {
            'layer-post': 'post',
            'layer-post-track': 'postTrack',
            'layer-pre': 'pre',
            'layer-pre-track': 'preTrack',
            'layer-basemap': 'basemap'
        };
        Object.keys(layerMap).forEach(function (id) {
            var input = byId(id);
            if (!input) { return; }
            input.addEventListener('change', function () {
                state.layers[layerMap[id]] = input.checked;
                var attrib = byId('map-attrib');
                if (attrib) { attrib.style.display = state.layers.basemap ? '' : 'none'; }
                requestDraw();
            });
        });

        var fit = byId('map-fit');
        if (fit) { fit.addEventListener('click', fitAll); }

        var follow = byId('map-follow');
        if (follow) {
            follow.addEventListener('click', function () {
                state.follow = !state.follow;
                syncFollowButton();
                if (state.follow) {
                    var fix = latestFix();
                    if (fix) { state.center = { lat: fix.lat, lon: fix.lon }; }
                }
                requestDraw();
            });
        }

        var zoomIn = byId('map-zoom-in');
        if (zoomIn) {
            zoomIn.addEventListener('click', function () { setZoom(state.zoom + 1, null); });
        }
        var zoomOut = byId('map-zoom-out');
        if (zoomOut) {
            zoomOut.addEventListener('click', function () { setZoom(state.zoom - 1, null); });
        }

        ['download-btn', 'download-btn-2'].forEach(function (id) {
            var button = byId(id);
            if (button) {
                button.addEventListener('click', function () {
                    window.location.href = 'api/history.csv';
                });
            }
        });

        ['clear-btn', 'clear-btn-2'].forEach(function (id) {
            var button = byId(id);
            if (button) { button.addEventListener('click', clearHistory); }
        });

        // The canvas has no layout while its section is hidden, so redraw as
        // soon as navigation brings the map back into view.
        var navTargets = [byId('homepage-link')].concat(
            Array.prototype.slice.call(document.querySelectorAll('.nav-item')));
        navTargets.forEach(function (target) {
            if (!target) { return; }
            target.addEventListener('click', function () {
                window.setTimeout(requestDraw, 0);
            });
        });
    }

    function clearHistory() {
        var name = (state.stats && state.stats.csv_name) || 'the recording file';
        var message = 'Clear all recorded location history?\n\n' +
            'This empties "' + name + '" on the router and the in-memory ' +
            'history, then starts a fresh recording for today. ' +
            'Download the CSV first if you want to keep it.';
        if (!window.confirm(message)) { return; }
        fetch('api/clear', { method: 'POST' })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                resetPoints(data && data.generation ? data.generation : state.generation + 1);
                poll();
            })
            .catch(function () {
                window.alert('Clear failed. Check the app log on the router.');
            });
    }

    function resetPoints(generation) {
        state.points = [];
        state.lastSeq = 0;
        state.generation = generation || 0;
        state.selected = null;
        renderSelected();
        renderSamplesTable();
        requestDraw();
    }

    // -------------------------------------------------------------- polling

    function poll() {
        if (state.polling) { return; }
        state.polling = true;
        fetch('api/points?since=' + state.lastSeq)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data) { return null; }
                if (state.generation && data.generation !== state.generation) {
                    state.points = [];
                    state.lastSeq = 0;
                    state.selected = null;
                }
                state.generation = data.generation;
                if (data.points && data.points.length) {
                    state.points = state.points.concat(data.points);
                }
                if (isNum(data.next)) { state.lastSeq = data.next; }
                // Keep the browser-side history aligned with the server cap.
                var cap = (state.info && state.info.max_points) || 7200;
                if (state.points.length > cap) {
                    state.points = state.points.slice(state.points.length - cap);
                }
                return fetch('api/status');
            })
            .then(function (response) { return response ? response.json() : null; })
            .then(function (data) {
                if (data) {
                    state.latest = data.latest;
                    state.stats = data.stats;
                    renderAll(data);
                }
                if (state.follow) {
                    var fix = latestFix();
                    if (fix) { state.center = { lat: fix.lat, lon: fix.lon }; }
                }
                requestDraw();
            })
            .catch(function () {
                /* transient fetch failure; the next tick retries */
            })
            .then(function () {
                state.polling = false;
            });
    }

    // ------------------------------------------------------------ rendering

    function renderRecordingName() {
        var name = (state.stats && state.stats.csv_name) || '';
        ['download-btn', 'download-btn-2'].forEach(function (id) {
            var button = byId(id);
            if (button && name) { button.title = 'Download "' + name + '"'; }
        });
        var note = byId('recording-file-note');
        if (note) {
            note.innerHTML = name
                ? 'Recording to <code>' + escapeHtml(name) +
                  '</code> \u2014 one file per day, kept open across midnight.'
                : '';
        }
    }

    /* Note which fix qualities have actually been seen, so the legend can add
     * an "Unknown" swatch if a code outside the table ever gets plotted.
     * Redraws the legend only when the set grows. */
    function trackObservedQualities() {
        var stats = state.stats;
        if (!stats) { return; }
        var grew = false;
        [stats.post_quality_counts, stats.pre_quality_counts].forEach(
            function (counts) {
                Object.keys(counts || {}).forEach(function (code) {
                    if (!state.observedQualities[code]) {
                        state.observedQualities[code] = true;
                        grew = true;
                    }
                });
            });
        if (grew) { renderLegend(); }
    }

    function renderAll(payload) {
        renderBanner(payload);
        renderRecordingName();
        trackObservedQualities();
        renderTiles();
        renderCompareTable();
        renderRtkStatus();
        renderAnalytics();
        renderSamplesTable();
    }

    function renderBanner(payload) {
        var banner = byId('rtk-banner');
        if (!banner) { return; }
        var messages = [];
        if (payload && payload.rtk_supported === false) {
            messages.push('This router does not expose <code>status/rtk</code>. ' +
                'RTK is unavailable, so only pre-correction positions are recorded.');
        }
        var latest = state.latest;
        var correction = latest && latest.rtk && latest.rtk.correction;
        if (correction && correction.error) {
            messages.push('Correction source error: ' + escapeHtml(correction.error));
        } else if (correction && correction.state &&
                correction.state !== 'streaming' && correction.state !== 'connected') {
            messages.push('Correction source state: <strong>' +
                escapeHtml(correction.state) + '</strong>');
        }
        if (latest && !latest.pre) {
            messages.push('No raw modem GNSS sentences found, so the ' +
                'pre-correction position is unavailable.');
        }
        // Fix quality and fix mode are NOT reported here. They change from one
        // second to the next (Float <-> DGPS), so a banner for them appears and
        // disappears constantly and reflows the whole page. They live in the
        // fixed-height fix tile instead.
        if (state.stats && state.stats.csv_writable === false) {
            messages.push('The recording file is not writable \u2014 samples are ' +
                'not being saved to CSV.');
        }
        if (state.stats && state.stats.last_error) {
            messages.push('Last error: ' + escapeHtml(state.stats.last_error));
        }
        // Debounce whatever is left. A dropped NMEA checksum or a brief
        // reconnect would otherwise flash a banner for a single poll and shift
        // the page twice. A state has to persist, or clear, for several polls
        // before the banner follows it.
        var key = messages.join('|');
        if (key !== state.bannerShown) {
            if (key === state.bannerPending) {
                state.bannerPendingCount += 1;
            } else {
                state.bannerPending = key;
                state.bannerPendingCount = 1;
            }
            if (state.bannerPendingCount < BANNER_DEBOUNCE_POLLS) { return; }
            state.bannerShown = key;
        }

        if (!messages.length) {
            banner.hidden = true;
            banner.innerHTML = '';
            return;
        }
        banner.hidden = false;
        banner.innerHTML = messages.join('<br>');
    }

    function renderTiles() {
        var latest = state.latest;
        var stats = state.stats || {};
        var post = (latest && latest.post) || null;
        var pre = (latest && latest.pre) || null;
        var rtk = (latest && latest.rtk) || {};
        var corrections = rtk.corrections || {};
        var accuracy = (latest && latest.accuracy) || {};
        var delta = (latest && latest.delta) || {};

        var qualityEl = byId('stat-fix-quality');
        var qualitySub = byId('stat-fix-sub');
        var tile = byId('tile-quality');
        if (qualityEl) {
            if (post) {
                var color = qualityColor(post.quality);
                qualityEl.innerHTML = qualityBadge(post.quality, post.quality_label);
                if (tile) {
                    tile.classList.add('rtk-tile-accent');
                    tile.style.borderLeftColor = color;
                }
            } else {
                qualityEl.textContent = '\u2014';
            }
        }
        if (qualitySub) {
            if (post) {
                // Kept short and on one line: this element has a reserved
                // height so the tile never changes size as the fix changes.
                var parts = ['q' + post.quality];
                if (post.quality_accuracy) { parts.push('~' + post.quality_accuracy); }
                if (post.fix_mode_label) { parts.push(post.fix_mode_label); }
                if (post.converging) { parts.push('converging'); }
                if (isNum(post.fix_mode) && post.fix_mode === 2) {
                    parts.push('altitude unreliable');
                }
                qualitySub.textContent = parts.join('  \u00b7  ');
                qualitySub.title = post.converging
                    ? 'RTK Float: carrier-phase ambiguities are not fully ' +
                      'resolved, so the solution is still converging toward ' +
                      'RTK Fixed (normally 10-60 s). Accuracy is 10-30 cm ' +
                      'until it does. Wait for Fixed before treating points ' +
                      'as survey grade.'
                    : 'Corrected fix quality from status/rtk/gnss';
            } else {
                qualitySub.textContent = 'no corrected fix';
                qualitySub.title = '';
            }
        }

        setText('stat-offset', fmtMeters(delta.horizontal_m, 3));
        setText('stat-offset-sub', isNum(delta.vertical_m)
            ? 'vertical ' + fmtMeters(delta.vertical_m, 3) +
              (isNum(delta.bearing_deg) ? '  \u00b7  ' + delta.bearing_deg.toFixed(0) + '\u00b0' : '')
            : 'horizontal pre \u2192 post');

        setText('stat-accuracy',
            fmtMetersPair(accuracy.horizontal_m, accuracy.vertical_m, 2));

        setText('stat-corr-age', isNum(corrections.age_s)
            ? corrections.age_s.toFixed(1) + ' s' : '\u2014');
        setText('stat-corr-sub', isNum(rtk.diff_age_s)
            ? 'GGA diff age ' + rtk.diff_age_s.toFixed(1) + ' s'
            : 'RTCM stream');

        setText('stat-sats', (post && isNum(post.satellites) ? post.satellites : '\u2014') +
            ' / ' + (pre && isNum(pre.satellites) ? pre.satellites : '\u2014'));

        setText('stat-samples', isNum(stats.samples) ? String(stats.samples) : '0');
        setText('stat-samples-sub', isNum(stats.duration_s)
            ? fmtDuration(stats.duration_s) + ' recorded' : '\u2014');
    }

    function setText(id, text) {
        var el = byId(id);
        if (el) { el.textContent = text; }
    }

    function setHtml(id, html) {
        var el = byId(id);
        if (el) { el.innerHTML = html; }
    }

    function renderCompareTable() {
        var body = byId('compare-body');
        if (!body) { return; }
        var latest = state.latest;
        if (!latest) {
            body.innerHTML = '<tr><td colspan="4" class="rtk-empty">' +
                'Waiting for the first sample\u2026</td></tr>';
            return;
        }
        var pre = latest.pre || {};
        var post = latest.post || {};
        var delta = latest.delta || {};

        function coord(value) {
            return isNum(value) ? value.toFixed(7) : '\u2014';
        }

        var rows = [
            ['Latitude', coord(pre.lat), coord(post.lat),
                isNum(delta.north_m) ? fmtMeters(delta.north_m, 3) + ' N' : '\u2014'],
            ['Longitude', coord(pre.lon), coord(post.lon),
                isNum(delta.east_m) ? fmtMeters(delta.east_m, 3) + ' E' : '\u2014'],
            ['Altitude (MSL)', fmt(pre.alt_m, 3, ' m'), fmt(post.alt_m, 3, ' m'),
                fmtMeters(delta.vertical_m, 3)],
            ['Fix quality',
                preQualityTag(pre.quality_label),
                qualityBadge(post.quality, post.quality_label || '\u2014'),
                '\u2014'],
            ['Typical accuracy', escapeHtml(pre.quality_accuracy || '\u2014'),
                escapeHtml(post.quality_accuracy || '\u2014'), '\u2014'],
            ['Fix mode (GSA)', escapeHtml(pre.fix_mode_label || '\u2014'),
                escapeHtml(post.fix_mode_label || '\u2014'), '\u2014'],
            ['Satellites', fmtInt(pre.satellites), fmtInt(post.satellites),
                (isNum(pre.satellites) && isNum(post.satellites))
                    ? (post.satellites - pre.satellites > 0 ? '+' : '') +
                      (post.satellites - pre.satellites) : '\u2014'],
            ['HDOP', fmt(pre.hdop, 2), fmt(post.hdop, 2), '\u2014'],
            ['VDOP', fmt(pre.vdop, 2), fmt(post.vdop, 2), '\u2014'],
            ['PDOP', fmt(pre.pdop, 2), fmt(post.pdop, 2), '\u2014'],
            ['Horizontal offset', '\u2014', '\u2014',
                isNum(delta.horizontal_m)
                    ? '<strong>' + escapeHtml(fmtMeters(delta.horizontal_m, 3)) +
                      '</strong>' : '\u2014'],
            ['3D offset', '\u2014', '\u2014', fmtMeters(delta.three_d_m, 3)]
        ];

        var html = '';
        rows.forEach(function (row) {
            html += '<tr><td>' + escapeHtml(row[0]) + '</td>' +
                '<td class="rtk-num">' + row[1] + '</td>' +
                '<td class="rtk-num">' + row[2] + '</td>' +
                '<td class="rtk-num">' + row[3] + '</td></tr>';
        });
        html += '<tr><td>Sample time</td><td colspan="3">' +
            escapeHtml(latest.timestamp_local || '') + ' ' +
            escapeHtml(latest.utc_offset || '') + '</td></tr>';
        body.innerHTML = html;
    }

    function renderRtkStatus() {
        var latest = state.latest;
        var rtk = (latest && latest.rtk) || {};
        var correction = rtk.correction || {};
        var corrections = rtk.corrections || {};
        var mqtt = rtk.mqtt || {};
        var info = state.info || {};
        var config = info.rtk_config || {};

        setHtml('source-detail', kvRows([
            { label: 'RTK enabled', value: rtk.enabled === null || rtk.enabled === undefined
                ? '\u2014' : (rtk.enabled ? 'Yes' : 'No') },
            { label: 'Source type', value: correction.type || '\u2014' },
            { label: 'Protocol format', value: correction.format || '\u2014' },
            { label: 'State', html: '<strong class="' +
                stateClass(correction.state) + '">' +
                escapeHtml(correction.state || '\u2014') + '</strong>' },
            { label: 'Error', value: correction.error || 'none' },
            { label: 'Caster', value: correction.host
                ? correction.host + ':' + correction.port : '\u2014' },
            { label: 'Mountpoint', value: correction.mountpoint || '\u2014' },
            { label: 'Connected for', value: fmtDuration(correction.uptime_s) },
            { label: 'Retry interval', value: isNum(correction.retry_interval_s)
                ? correction.retry_interval_s + ' s' : 'n/a' },
            { label: 'GGA uplink rate', value: isNum(correction.gga_rate_s)
                ? 'every ' + correction.gga_rate_s + ' s' : '\u2014' },
            { label: 'Last GGA sent', value: isNum(correction.last_gga_age_s)
                ? correction.last_gga_age_s.toFixed(1) + ' s ago' : '\u2014' },
            { label: 'GGA send failures', value: fmtInt(correction.gga_send_failures) }
        ]));

        setHtml('corrections-detail', kvRows([
            { label: 'RTCM frames received', value: fmtInt(corrections.frames_total) },
            { label: 'Frames dropped', html: '<strong class="' +
                (corrections.frames_dropped ? 'rtk-warn' : 'rtk-ok') + '">' +
                escapeHtml(fmtInt(corrections.frames_dropped)) + '</strong>' },
            { label: 'Frames queued', value: fmtInt(corrections.frames_queued) },
            { label: 'CRC failures', html: '<strong class="' +
                (corrections.crc_failures ? 'rtk-warn' : 'rtk-ok') + '">' +
                escapeHtml(fmtInt(corrections.crc_failures)) + '</strong>' },
            { label: 'Bytes received', value: fmtBytes(corrections.bytes_received) },
            { label: 'Last frame', value: isNum(corrections.age_s)
                ? corrections.age_s.toFixed(1) + ' s ago' : '\u2014' },
            { label: 'MQTT connected', value: mqtt.connected === null ||
                mqtt.connected === undefined ? '\u2014' : (mqtt.connected ? 'Yes' : 'No') },
            { label: 'MQTT publish failures', value: fmtInt(mqtt.publish_failures) }
        ]));

        var post = (latest && latest.post) || {};
        var pre = (latest && latest.pre) || {};
        var accuracy = (latest && latest.accuracy) || {};
        var motion = (latest && latest.motion) || {};
        setHtml('gnss-detail', kvRows([
            { label: 'Router fix_quality', value: rtk.fix_quality || '\u2014' },
            { label: 'Corrected GGA quality', value: isNum(post.quality)
                ? post.quality + ' \u2013 ' + qualityLabel(post.quality) +
                  ' (~' + (post.quality_accuracy || '?') + ')' : '\u2014' },
            { label: 'Held this quality for', value: fmtDuration(post.quality_held_s) },
            { label: 'Pre-correction GGA quality', value: isNum(pre.quality)
                ? pre.quality + ' \u2013 ' + qualityLabel(pre.quality) +
                  ' (~' + (pre.quality_accuracy || '?') + ')' : '\u2014' },
            { label: 'Fix mode (corrected)', value: post.fix_mode_label || '\u2014' },
            { label: 'Fix mode (raw modem)', value: pre.fix_mode_label || '\u2014' },
            { label: 'Differential age', value: isNum(rtk.diff_age_s)
                ? rtk.diff_age_s.toFixed(1) + ' s' : '\u2014' },
            { label: 'Reference station', value: rtk.ref_station_id || '\u2014' },
            { label: 'Satellites (corrected)', value: fmtInt(post.satellites) },
            { label: 'Satellites (raw modem)', value: fmtInt(pre.satellites) },
            { label: 'HDOP / VDOP / PDOP (corrected)',
                value: fmt(post.hdop, 2) + ' / ' + fmt(post.vdop, 2) +
                       ' / ' + fmt(post.pdop, 2) },
            { label: 'HDOP / VDOP / PDOP (raw modem)',
                value: fmt(pre.hdop, 2) + ' / ' + fmt(pre.vdop, 2) +
                       ' / ' + fmt(pre.pdop, 2) },
            { label: 'Horizontal accuracy', value: fmtMeters(accuracy.horizontal_m, 2) },
            { label: 'Vertical accuracy', value: fmtMeters(accuracy.vertical_m, 2) },
            { label: 'Speed accuracy', value: fmt(accuracy.speed_m_s, 2, ' m/s') },
            { label: 'Reported accuracy', value: fmtMeters(accuracy.reported_m, 2) },
            { label: 'Ground speed', value: fmt(motion.speed_kph, 2, ' km/h') },
            { label: 'Heading', value: fmt(motion.heading_deg, 1, '\u00b0') },
            { label: 'Raw GNSS source', value: (latest && latest.gps_device) || '\u2014' }
        ]));

        setHtml('config-detail', kvRows([
            { label: 'Configured source', value: config.source || '\u2014' },
            { label: 'Enabled in config', value: config.enabled === null ||
                config.enabled === undefined ? '\u2014' : (config.enabled ? 'Yes' : 'No') },
            { label: 'NTRIP host', value: config.host || '\u2014' },
            { label: 'NTRIP port', value: isNum(config.port) ? config.port : '\u2014' },
            { label: 'Mountpoint', value: config.mountpoint || '\u2014' },
            { label: 'Format', value: config.format || '\u2014' },
            { label: 'GGA rate', value: isNum(config.gga_rate)
                ? config.gga_rate + ' s' : '\u2014' },
            { label: 'Username', value: config.username || '\u2014' }
        ]));

        var types = corrections.msg_types_seen || [];
        if (types.length) {
            setHtml('msgtypes-detail', types.map(function (type) {
                return '<span class="rtk-chip">' + escapeHtml(type) + '</span>';
            }).join(''));
        } else {
            setHtml('msgtypes-detail',
                '<p class="rtk-empty">No RTCM message types reported yet.</p>');
        }

        setText('nmea-pre', (pre && pre.sentence) || '\u2014');
        setText('nmea-post', (post && post.sentence) || '\u2014');
    }

    function stateClass(stateName) {
        if (!stateName) { return ''; }
        if (stateName === 'streaming' || stateName === 'connected') { return 'rtk-ok'; }
        if (stateName === 'error' || stateName === 'failed') { return 'rtk-bad'; }
        return 'rtk-warn';
    }

    function renderAnalytics() {
        var stats = state.stats;
        if (!stats) { return; }
        var delta = stats.delta || {};

        setHtml('delta-stats', kvRows([
            { label: 'Samples with both fixes', value: fmtInt(delta.count) },
            { label: 'Last offset', value: fmtMeters(delta.last_m, 3) },
            { label: 'Mean offset', value: fmtMeters(delta.mean_m, 3) },
            { label: 'Minimum offset', value: fmtMeters(delta.min_m, 3) },
            { label: 'Maximum offset', value: fmtMeters(delta.max_m, 3) },
            { label: 'Mean vertical offset', value: fmtMeters(delta.vertical_mean_m, 3) },
            { label: 'Last vertical offset', value: fmtMeters(delta.vertical_last_m, 3) }
        ]));

        renderDistribution('quality-dist', stats.post_quality_counts,
            stats.pre_quality_counts);

        setHtml('post-spread', spreadRows(stats.post_spread));
        setHtml('pre-spread', spreadRows(stats.pre_spread));

        setHtml('recording-stats', kvRows([
            { label: 'In-memory samples', value: fmtInt(stats.samples) +
                ' of ' + fmtInt(stats.max_points) },
            { label: 'Rows written to CSV', value: fmtInt(stats.rows_written) },
            { label: 'Repeat GNSS epochs skipped', value: fmtInt(stats.duplicates_skipped) },
            { label: 'Recording file', html: '<code>' +
                escapeHtml(stats.csv_name || '\u2014') + '</code>' },
            { label: 'File size', value: fmtBytes(stats.csv_bytes) },
            { label: 'Writable', html: '<strong class="' +
                (stats.csv_writable ? 'rtk-ok' : 'rtk-bad') + '">' +
                (stats.csv_writable ? 'Yes' : 'No') + '</strong>' },
            { label: 'Sample interval', value: fmt(stats.interval_s, 2, ' s') },
            { label: 'Recorded span', value: fmtDuration(stats.duration_s) },
            { label: 'App uptime', value: fmtDuration(stats.uptime_s) },
            { label: 'Read errors', value: fmtInt(stats.errors) },
            { label: 'Last error', value: stats.last_error || 'none' }
        ]));
    }

    function spreadRows(spread) {
        if (!spread || !spread.count) {
            return '<p class="rtk-empty">Not enough samples yet.</p>';
        }
        return kvRows([
            { label: 'Samples', value: fmtInt(spread.count) },
            { label: 'Mean position', value: isNum(spread.mean_lat)
                ? spread.mean_lat.toFixed(7) + ', ' + spread.mean_lon.toFixed(7) : '\u2014' },
            { label: 'Sigma east', value: fmtMeters(spread.sigma_east_m, 3) },
            { label: 'Sigma north', value: fmtMeters(spread.sigma_north_m, 3) },
            { label: 'DRMS (~65%)', value: fmtMeters(spread.drms_m, 3) },
            { label: '2DRMS (~95%)', value: fmtMeters(spread.twodrms_m, 3) },
            { label: 'CEP50', value: fmtMeters(spread.cep50_m, 3) },
            { label: 'Max radial error', value: fmtMeters(spread.max_radial_m, 3) },
            { label: 'Mean altitude', value: fmt(spread.mean_alt_m, 3, ' m') },
            { label: 'Sigma altitude', value: fmtMeters(spread.sigma_alt_m, 3) }
        ]);
    }

    function renderDistribution(elementId, postCounts, preCounts) {
        var el = byId(elementId);
        if (!el) { return; }
        var keys = Object.keys(postCounts || {});
        if (!keys.length) {
            el.innerHTML = '<p class="rtk-empty">No samples yet.</p>';
            return;
        }
        var total = 0;
        keys.forEach(function (key) { total += postCounts[key]; });
        keys.sort(function (a, b) { return postCounts[b] - postCounts[a]; });

        var html = '<p class="rtk-tile-label">Corrected fixes</p>';
        keys.forEach(function (key) {
            var count = postCounts[key];
            var percent = total ? (count * 100 / total) : 0;
            html += '<div class="rtk-dist-row">' +
                '<span title="typical accuracy ' + escapeHtml(qualityAccuracy(key)) +
                    '"><span class="rtk-legend-dot" style="background:' +
                    qualityColor(key) + '"></span> ' + escapeHtml(qualityLabel(key)) +
                    (qualityAccuracy(key) ? ' <span class="rtk-legend-acc">~' +
                        escapeHtml(qualityAccuracy(key)) + '</span>' : '') + '</span>' +
                '<span class="rtk-dist-track"><span class="rtk-dist-fill" style="width:' +
                    percent.toFixed(1) + '%;background:' + qualityColor(key) + '"></span></span>' +
                '<span class="rtk-dist-value">' + percent.toFixed(1) + '% (' + count + ')</span>' +
                '</div>';
        });

        var preKeys = Object.keys(preCounts || {});
        if (preKeys.length) {
            var preTotal = 0;
            preKeys.forEach(function (key) { preTotal += preCounts[key]; });
            preKeys.sort(function (a, b) { return preCounts[b] - preCounts[a]; });
            html += '<p class="rtk-tile-label" style="margin-top:0.75rem">' +
                'Pre-correction fixes</p>';
            preKeys.forEach(function (key) {
                var count = preCounts[key];
                var percent = preTotal ? (count * 100 / preTotal) : 0;
                html += '<div class="rtk-dist-row">' +
                    '<span><span class="rtk-legend-dot rtk-legend-pre" style="background:' +
                        state.preColor + '"></span> ' + escapeHtml(qualityLabel(key)) + '</span>' +
                    '<span class="rtk-dist-track"><span class="rtk-dist-fill" style="width:' +
                        percent.toFixed(1) + '%;background:' + state.preColor + '"></span></span>' +
                    '<span class="rtk-dist-value">' + percent.toFixed(1) + '% (' + count + ')</span>' +
                    '</div>';
            });
        }
        el.innerHTML = html;
    }

    function renderSamplesTable() {
        var body = byId('samples-body');
        if (!body) { return; }
        if (!state.points.length) {
            body.innerHTML = '<tr><td colspan="11" class="rtk-empty">No samples yet.</td></tr>';
            return;
        }
        var rows = state.points.slice(-SAMPLE_TABLE_ROWS).reverse();
        var html = '';
        rows.forEach(function (point) {
            var time = new Date(point[I_TS] * 1000);
            html += '<tr>' +
                '<td class="rtk-num">' + point[I_SEQ] + '</td>' +
                '<td class="rtk-num">' + escapeHtml(time.toLocaleTimeString()) + '</td>' +
                '<td class="rtk-num">' + (isNum(point[I_PRE_LAT]) ? point[I_PRE_LAT].toFixed(7) : '\u2014') + '</td>' +
                '<td class="rtk-num">' + (isNum(point[I_PRE_LON]) ? point[I_PRE_LON].toFixed(7) : '\u2014') + '</td>' +
                '<td class="rtk-num">' + fmt(point[I_PRE_ALT], 2) + '</td>' +
                '<td class="rtk-num">' + (isNum(point[I_POST_LAT]) ? point[I_POST_LAT].toFixed(7) : '\u2014') + '</td>' +
                '<td class="rtk-num">' + (isNum(point[I_POST_LON]) ? point[I_POST_LON].toFixed(7) : '\u2014') + '</td>' +
                '<td class="rtk-num">' + fmt(point[I_POST_ALT], 2) + '</td>' +
                '<td>' + qualityBadge(point[I_POST_Q]) + '</td>' +
                '<td class="rtk-num">' + fmt(point[I_DH], 3) + '</td>' +
                '<td class="rtk-num">' + fmt(point[I_DV], 3) + '</td>' +
                '</tr>';
        });
        body.innerHTML = html;
    }

    function renderSelected() {
        var el = byId('selected-detail');
        if (!el) { return; }
        if (!state.selected) {
            el.innerHTML = '<p class="rtk-empty">Click a point on the map to inspect it.</p>';
            return;
        }
        var point = state.selected.point;
        var isPre = state.selected.kind === 'pre';
        var time = new Date(point[I_TS] * 1000);
        el.innerHTML = kvRows([
            { label: 'Layer', html: isPre
                ? '<strong><span class="rtk-legend-dot rtk-legend-pre" style="background:' +
                    state.preColor + '"></span> Pre-correction</strong>'
                : '<strong><span class="rtk-legend-dot" style="background:' +
                    qualityColor(point[I_POST_Q]) + '"></span> Corrected</strong>' },
            { label: 'Sample #', value: point[I_SEQ] },
            { label: 'Time', value: time.toLocaleString() },
            { label: 'Latitude', value: isNum(isPre ? point[I_PRE_LAT] : point[I_POST_LAT])
                ? (isPre ? point[I_PRE_LAT] : point[I_POST_LAT]).toFixed(8) : '\u2014' },
            { label: 'Longitude', value: isNum(isPre ? point[I_PRE_LON] : point[I_POST_LON])
                ? (isPre ? point[I_PRE_LON] : point[I_POST_LON]).toFixed(8) : '\u2014' },
            { label: 'Altitude', value: fmt(isPre ? point[I_PRE_ALT] : point[I_POST_ALT], 3, ' m') },
            { label: 'Fix quality', value: qualityLabel(isPre ? point[I_PRE_Q] : point[I_POST_Q]) },
            { label: 'Typical accuracy',
                value: qualityAccuracy(isPre ? point[I_PRE_Q] : point[I_POST_Q]) || '\u2014' },
            { label: 'Horizontal offset', value: fmtMeters(point[I_DH], 3) },
            { label: 'Vertical offset', value: fmtMeters(point[I_DV], 3) },
            { label: 'Horizontal accuracy', value: fmtMeters(point[I_HACC], 2) }
        ]);
    }

    function renderLegend() {
        var el = byId('rtk-legend');
        if (!el || !state.legend) { return; }
        var html = '<span class="rtk-legend-item">' +
            '<span class="rtk-legend-dot rtk-legend-pre" style="background:' +
            state.preColor + '"></span> Pre-correction (raw modem GNSS)</span>';
        // Server order is worst-to-best, so RTK Fixed lands on the right.
        var known = {};
        (state.legend.qualities || []).forEach(function (entry) {
            known[String(entry.code)] = true;
            html += '<span class="rtk-legend-item" title="GGA quality ' +
                entry.code + ' \u2014 typical accuracy ' +
                escapeHtml(entry.accuracy || '') + '">' +
                '<span class="rtk-legend-dot" style="background:' + entry.color +
                '"></span> ' + escapeHtml(entry.label) +
                (entry.accuracy ? ' <span class="rtk-legend-acc">' +
                    escapeHtml(entry.accuracy) + '</span>' : '') +
                '</span>';
        });

        // Only if a quality outside the table has actually been plotted, so a
        // colour on the map is never left unexplained.
        var unknown = state.legend.unknown;
        var sawUnknown = Object.keys(state.observedQualities).some(
            function (code) { return !known[code]; });
        if (unknown && sawUnknown) {
            html += '<span class="rtk-legend-item">' +
                '<span class="rtk-legend-dot" style="background:' +
                unknown.color + '"></span> ' + escapeHtml(unknown.label) +
                '</span>';
        }
        el.innerHTML = html;
    }

    // ----------------------------------------------------------------- init

    function loadInfo() {
        return fetch('api/info')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data) { return; }
                state.info = data;
                var legend = data.legend || {};
                state.legend = legend;
                state.preColor = legend.pre_color || FALLBACK_PRE_COLOR;
                (legend.qualities || []).forEach(function (entry) {
                    state.qualityColors[String(entry.code)] = entry.color;
                    state.qualityLabels[String(entry.code)] = entry.label;
                    state.qualityAccuracy[String(entry.code)] = entry.accuracy;
                });
                setText('header-router-name', data.router_name || '\u2014');
                setText('header-ncos-version', data.firmware_version || '\u2014');
                var title = byId('app-title');
                if (title && data.router_model) {
                    title.title = data.router_model;
                }
                renderLegend();
            })
            .catch(function () {
                /* header values stay as placeholders */
            });
    }

    function init() {
        canvas = byId('rtk-map');
        if (canvas) {
            ctx = canvas.getContext('2d');
            bindMapEvents();
        }
        bindControls();
        syncFollowButton();
        loadInfo().then(function () {
            poll();
            window.setInterval(poll, POLL_MS);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
