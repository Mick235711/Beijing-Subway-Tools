window.routeMapSetup = window.routeMapSetup || function(id) {
    const root = document.getElementById(id);
    if (!root) return;
    if (root._routeMapState) return;
    const image = root.querySelector('img');
    const svg = root.querySelector('svg');
    if (!image || !svg) return;
    const baseViewBox = (svg.getAttribute('viewBox') || '').trim().split(/\s+/).map(Number);
    if (
        baseViewBox.length !== 4 || baseViewBox.some(value => !Number.isFinite(value)) ||
        baseViewBox[2] <= 0 || baseViewBox[3] <= 0
    ) {
        if (!root._routeMapSetupPending) {
            root._routeMapSetupPending = true;
            window.requestAnimationFrame(() => {
                root._routeMapSetupPending = false;
                if (root.isConnected) window.routeMapSetup(id);
            });
        }
        return;
    }

    const state = root._routeMapState = {
        scale: 1,
        x: 0,
        y: 0,
        pointers: new Map(),
        moved: false,
        frame: null
    };
    const tooltip = document.createElement('div');
    tooltip.className = 'route-map-tooltip';
    root.appendChild(tooltip);

    const clamp = () => {
        const width = root.clientWidth;
        const height = root.clientHeight;
        state.x = Math.min(0, Math.max(width - width * state.scale, state.x));
        state.y = Math.min(0, Math.max(height - height * state.scale, state.y));
    };
    const render = () => {
        state.frame = null;
        clamp();
        root.style.setProperty('--route-map-x', `${state.x}px`);
        root.style.setProperty('--route-map-y', `${state.y}px`);
        root.style.setProperty('--route-map-scale', `${state.scale}`);
        root.style.setProperty('--route-map-path-width', `${state.scale * 5}px`);
        const width = root.clientWidth;
        const height = root.clientHeight;
        if (width > 0 && height > 0) {
            const viewWidth = baseViewBox[2] / state.scale;
            const viewHeight = baseViewBox[3] / state.scale;
            const viewX = baseViewBox[0] - state.x * baseViewBox[2] / (width * state.scale);
            const viewY = baseViewBox[1] - state.y * baseViewBox[3] / (height * state.scale);
            svg.setAttribute('viewBox', `${viewX} ${viewY} ${viewWidth} ${viewHeight}`);
        }
        root.classList.toggle('route-map-zoomed', state.scale >= 2.1);
    };
    const apply = () => {
        if (state.frame === null) state.frame = window.requestAnimationFrame(render);
    };
    root._routeMapApply = apply;
    const zoomAt = (factor, clientX, clientY) => {
        const rect = root.getBoundingClientRect();
        const px = clientX - rect.left;
        const py = clientY - rect.top;
        const previous = state.scale;
        const nextScale = state.scale * factor;
        state.scale = Math.min(6, Math.max(1, nextScale));
        const ratio = state.scale / previous;
        state.x = px - (px - state.x) * ratio;
        state.y = py - (py - state.y) * ratio;
        apply();
    };
    root._routeMapZoom = factor => {
        const rect = root.getBoundingClientRect();
        zoomAt(factor, rect.left + rect.width / 2, rect.top + rect.height / 2);
    };
    root._routeMapReset = () => {
        state.scale = 1;
        state.x = 0;
        state.y = 0;
        apply();
    };
    new ResizeObserver(apply).observe(root);

    root.addEventListener('wheel', event => {
        event.preventDefault();
        zoomAt(event.deltaY < 0 ? 1.18 : 1 / 1.18, event.clientX, event.clientY);
    }, {passive: false});

    root.addEventListener('pointerdown', event => {
        state.pointers.set(event.pointerId, {
            x: event.clientX,
            y: event.clientY,
            startX: event.clientX,
            startY: event.clientY
        });
        state.moved = false;
        if (state.pointers.size === 2) {
            const points = [...state.pointers.values()];
            state.pinchDistance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
            state.moved = true;
        }
    }, true);
    root.addEventListener('pointermove', event => {
        const previous = state.pointers.get(event.pointerId);
        if (!previous) return;
        if (Math.hypot(event.clientX - previous.startX, event.clientY - previous.startY) > 4) {
            state.moved = true;
            if (!root.hasPointerCapture(event.pointerId)) root.setPointerCapture(event.pointerId);
        }
        state.pointers.set(event.pointerId, {
            x: event.clientX,
            y: event.clientY,
            startX: previous.startX,
            startY: previous.startY
        });
        if (state.pointers.size === 1 && state.scale > 1 && state.moved) {
            state.x += event.clientX - previous.x;
            state.y += event.clientY - previous.y;
            apply();
        } else if (state.pointers.size === 2) {
            const points = [...state.pointers.values()];
            const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
            const middleX = (points[0].x + points[1].x) / 2;
            const middleY = (points[0].y + points[1].y) / 2;
            if (state.pinchDistance) zoomAt(distance / state.pinchDistance, middleX, middleY);
            state.pinchDistance = distance;
        }
    }, true);
    const finishPointer = event => {
        if (state.moved) {
            event.preventDefault();
            event.stopPropagation();
        }
        state.pointers.delete(event.pointerId);
        state.pinchDistance = null;
        if (state.pointers.size === 0) state.moved = false;
    };
    root.addEventListener('pointerup', finishPointer, true);
    root.addEventListener('pointercancel', finishPointer, true);

    root.addEventListener('pointerover', event => {
        const hit = event.target.closest?.('.route-map-hit');
        if (!hit) return;
        tooltip.replaceChildren();
        const name = document.createElement('strong');
        name.textContent = hit.dataset.station;
        tooltip.appendChild(name);
        const lines = document.createElement('div');
        lines.className = 'route-map-tooltip-lines';
        for (const [label, color, textColor] of JSON.parse(hit.dataset.lines || '[]')) {
            const badge = document.createElement('span');
            badge.className = 'route-map-tooltip-badge';
            badge.textContent = label;
            badge.style.background = color;
            badge.style.color = textColor;
            lines.appendChild(badge);
        }
        tooltip.appendChild(lines);
        tooltip.style.display = 'block';
    });
    root.addEventListener('pointermove', event => {
        if (tooltip.style.display !== 'block') return;
        const rect = root.getBoundingClientRect();
        tooltip.style.left = `${Math.min(root.clientWidth - tooltip.offsetWidth - 8, event.clientX - rect.left + 14)}px`;
        tooltip.style.top = `${Math.max(8, event.clientY - rect.top - tooltip.offsetHeight - 10)}px`;
    });
    root.addEventListener('pointerout', event => {
        if (event.target.closest?.('.route-map-hit')) tooltip.style.display = 'none';
    });
    apply();
};

window.routeMapZoom = function(id, factor) {
    document.getElementById(id)?._routeMapZoom?.(factor);
};

window.routeMapReset = function(id) {
    document.getElementById(id)?._routeMapReset?.();
};

window.routeMapStopAttachment = function(key) {
    const attachment = window._routeMapAttachments?.get(key);
    if (!attachment) return;
    attachment.observer.disconnect();
    window._routeMapAttachments.delete(key);
};

window.routeMapAttach = function(key, targetId, viewerId) {
    window._routeMapAttachments = window._routeMapAttachments || new Map();
    window.routeMapStopAttachment(key);

    const viewer = document.getElementById(viewerId);
    const app = document.querySelector('#app');
    if (!viewer || !app) return;
    const ensureAttached = () => {
        const target = document.getElementById(targetId);
        if (target && viewer.parentNode !== target) target.appendChild(viewer);
    };
    const observer = new MutationObserver(ensureAttached);
    observer.observe(app, {childList: true, subtree: true});
    window._routeMapAttachments.set(key, {observer, viewer});
    ensureAttached();
};

const startRouteMapObserver = () => {
    const app = document.querySelector('#app');
    if (!app) {
        window.setTimeout(startRouteMapObserver, 20);
        return;
    }
    if (!window._routeMapObserver) {
        window._routeMapObserver = new MutationObserver(() => {
            document.querySelectorAll('.route-map-image').forEach(root => window.routeMapSetup(root.id));
        });
        window._routeMapObserver.observe(app, {childList: true, subtree: true});
    }
    document.querySelectorAll('.route-map-image').forEach(root => window.routeMapSetup(root.id));
};

startRouteMapObserver();
