(function () {
    const ICON_MAP = {
        check: "\u2713",
        close: "\u2715",
        refresh: "\u21bb",
        star: "\u2605",
        info: "\u2139",
        warning: "\u26a0",
        error: "\u26d4",
        search: "\uD83D\uDD0D",
        home: "\uD83C\uDFE0",
        settings: "\u2699",
        mail: "\u2709",
        phone: "\u260E",
        calendar: "\uD83D\uDCC5",
        clock: "\u23F0",
        user: "\uD83D\uDC64",
        add: "+",
        delete: "\uD83D\uDDD1",
        edit: "\u270E",
        send: "\u27A4",
    };

    function isSafeMediaUrl(url) {
        if (!url || typeof url !== "string") {
            return false;
        }
        const trimmed = url.trim();
        if (trimmed.startsWith("/uploads/") || trimmed.startsWith("/static/")) {
            return true;
        }
        try {
            const parsed = new URL(trimmed, window.location.origin);
            return parsed.protocol === "https:" || parsed.protocol === "http:";
        } catch (err) {
            return false;
        }
    }

    function decodePointerSegment(seg) {
        return seg.replace(/~1/g, "/").replace(/~0/g, "~");
    }

    function getByPointer(dataModel, pointer) {
        if (!pointer || pointer === "/") {
            return dataModel;
        }
        const cleaned = pointer.startsWith("/") ? pointer.slice(1) : pointer;
        const segments = cleaned.split("/").map(decodePointerSegment);
        let current = dataModel;
        for (const seg of segments) {
            if (current === null || current === undefined) {
                return undefined;
            }
            current = current[seg];
        }
        return current;
    }

    function setByPointer(dataModel, pointer, value) {
        if (!pointer || pointer === "/") {
            if (value && typeof value === "object" && !Array.isArray(value)) {
                Object.assign(dataModel, value);
            }
            return;
        }
        const cleaned = pointer.startsWith("/") ? pointer.slice(1) : pointer;
        const segments = cleaned.split("/").map(decodePointerSegment);
        let current = dataModel;
        for (let i = 0; i < segments.length - 1; i += 1) {
            const key = segments[i];
            if (!current[key] || typeof current[key] !== "object") {
                current[key] = {};
            }
            current = current[key];
        }
        const lastKey = segments[segments.length - 1];
        if (value === null) {
            delete current[lastKey];
        } else {
            current[lastKey] = value;
        }
    }

    function getBindingPath(prop) {
        if (!prop || typeof prop !== "object") {
            return null;
        }
        if (typeof prop["@path"] === "string") {
            return prop["@path"];
        }
        if (typeof prop.path === "string") {
            return prop.path;
        }
        return null;
    }

    function resolveValue(surface, prop, fallback = undefined) {
        if (prop === undefined || prop === null) {
            return fallback;
        }
        if (typeof prop !== "object" || Array.isArray(prop)) {
            return prop;
        }
        const bindingPath = getBindingPath(prop);
        if (bindingPath) {
            const bound = getByPointer(surface.dataModel, bindingPath);
            if (bound !== undefined) {
                return bound;
            }
        }
        if ("literalString" in prop) return prop.literalString;
        if ("literalNumber" in prop) return prop.literalNumber;
        if ("literalBoolean" in prop) return prop.literalBoolean;
        if ("literalArray" in prop) return prop.literalArray;
        return fallback !== undefined ? fallback : prop;
    }

    function resolveContextObject(surface, rawContext) {
        if (!rawContext || typeof rawContext !== "object") {
            return {};
        }
        const resolved = {};
        for (const [key, val] of Object.entries(rawContext)) {
            resolved[key] = resolveValue(surface, val);
        }
        return resolved;
    }

    function applyJustifyAndAlign(el, comp) {
        const justifyMap = {
            start: "flex-start",
            center: "center",
            end: "flex-end",
            spaceBetween: "space-between",
            spaceAround: "space-around",
            spaceEvenly: "space-evenly",
        };
        const alignMap = {
            start: "flex-start",
            center: "center",
            end: "flex-end",
            stretch: "stretch",
        };
        if (comp.justify && justifyMap[comp.justify]) {
            el.style.justifyContent = justifyMap[comp.justify];
        }
        if (comp.align && alignMap[comp.align]) {
            el.style.alignItems = alignMap[comp.align];
        }
    }

    function renderComponent(surface, componentId, onAction, visited = new Set()) {
        if (!componentId || visited.has(componentId)) {
            return document.createTextNode("");
        }
        const comp = surface.components.get(componentId);
        if (!comp) {
            return document.createTextNode("");
        }

        const nextVisited = new Set(visited);
        nextVisited.add(componentId);

        const type = comp.component;

        switch (type) {
            case "Card": {
                const card = document.createElement("div");
                card.className = "a2ui-card";
                if (comp.child) {
                    card.appendChild(renderComponent(surface, comp.child, onAction, nextVisited));
                } else if (Array.isArray(comp.children)) {
                    for (const childId of comp.children) {
                        card.appendChild(renderComponent(surface, childId, onAction, nextVisited));
                    }
                }
                return card;
            }

            case "Row": {
                const row = document.createElement("div");
                row.className = "a2ui-row";
                applyJustifyAndAlign(row, comp);
                const children = Array.isArray(comp.children) ? comp.children : [];
                for (const childId of children) {
                    row.appendChild(renderComponent(surface, childId, onAction, nextVisited));
                }
                return row;
            }

            case "Column": {
                const col = document.createElement("div");
                col.className = "a2ui-column";
                applyJustifyAndAlign(col, comp);
                const children = Array.isArray(comp.children) ? comp.children : [];
                for (const childId of children) {
                    col.appendChild(renderComponent(surface, childId, onAction, nextVisited));
                }
                return col;
            }

            case "List": {
                const list = document.createElement("div");
                list.className = comp.direction === "horizontal" ? "a2ui-list horizontal" : "a2ui-list";
                applyJustifyAndAlign(list, comp);
                const children = Array.isArray(comp.children) ? comp.children : [];
                for (const childId of children) {
                    list.appendChild(renderComponent(surface, childId, onAction, nextVisited));
                }
                return list;
            }

            case "Divider": {
                const hr = document.createElement("hr");
                hr.className = comp.axis === "vertical" ? "a2ui-divider vertical" : "a2ui-divider";
                return hr;
            }

            case "Tabs": {
                const wrapper = document.createElement("div");
                wrapper.className = "a2ui-tabs";
                const items = Array.isArray(comp.tabs)
                    ? comp.tabs
                    : Array.isArray(comp.tabItems)
                      ? comp.tabItems
                      : [];
                if (items.length === 0) {
                    return wrapper;
                }

                const header = document.createElement("div");
                header.className = "a2ui-tabs-header";
                const panel = document.createElement("div");
                panel.className = "a2ui-tabs-panel";

                let activeIdx = 0;
                const renderTabBody = () => {
                    panel.innerHTML = "";
                    const currentTab = items[activeIdx];
                    if (currentTab && currentTab.child) {
                        panel.appendChild(renderComponent(surface, currentTab.child, onAction, nextVisited));
                    }
                    Array.from(header.children).forEach((btn, idx) => {
                        btn.classList.toggle("active", idx === activeIdx);
                    });
                };

                items.forEach((item, idx) => {
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = idx === 0 ? "a2ui-tab-btn active" : "a2ui-tab-btn";
                    btn.textContent = String(resolveValue(surface, item.title, `Tab ${idx + 1}`));
                    btn.addEventListener("click", () => {
                        activeIdx = idx;
                        renderTabBody();
                    });
                    header.appendChild(btn);
                });

                wrapper.appendChild(header);
                wrapper.appendChild(panel);
                renderTabBody();
                return wrapper;
            }

            case "Modal": {
                const container = document.createElement("div");
                container.className = "a2ui-modal-wrapper";
                const triggerId = comp.trigger || comp.entryPointChild;
                const contentId = comp.content || comp.contentChild;

                const triggerEl = renderComponent(surface, triggerId, () => {
                    const backdrop = document.createElement("div");
                    backdrop.className = "a2ui-modal-backdrop";

                    const dialog = document.createElement("div");
                    dialog.className = "a2ui-modal-dialog";
                    dialog.appendChild(renderComponent(surface, contentId, onAction, nextVisited));

                    const footer = document.createElement("div");
                    footer.className = "a2ui-modal-footer";
                    const closeBtn = document.createElement("button");
                    closeBtn.type = "button";
                    closeBtn.className = "a2ui-btn";
                    closeBtn.textContent = "Close";
                    closeBtn.addEventListener("click", () => backdrop.remove());
                    footer.appendChild(closeBtn);

                    dialog.appendChild(footer);
                    backdrop.appendChild(dialog);
                    backdrop.addEventListener("click", (ev) => {
                        if (ev.target === backdrop) {
                            backdrop.remove();
                        }
                    });
                    document.body.appendChild(backdrop);
                }, nextVisited);

                container.appendChild(triggerEl);
                return container;
            }

            case "Text": {
                const textEl = document.createElement("div");
                const variant = comp.variant || comp.usageHint || "body";
                textEl.className = `a2ui-text variant-${variant}`;
                textEl.textContent = String(resolveValue(surface, comp.text, ""));
                return textEl;
            }

            case "Icon": {
                const iconEl = document.createElement("span");
                iconEl.className = "a2ui-icon";
                const iconName = String(resolveValue(surface, comp.name, "info")).toLowerCase();
                iconEl.textContent = ICON_MAP[iconName] || "\u25CF";
                iconEl.title = iconName;
                return iconEl;
            }

            case "Image": {
                const url = String(resolveValue(surface, comp.url, ""));
                if (!isSafeMediaUrl(url)) {
                    const fallback = document.createElement("div");
                    fallback.className = "a2ui-text variant-caption";
                    fallback.textContent = "[Blocked or invalid image URL]";
                    return fallback;
                }
                const img = document.createElement("img");
                img.className = "a2ui-image";
                img.src = url;
                img.alt = String(resolveValue(surface, comp.alt, "A2UI Image"));
                if (comp.fit) {
                    img.style.objectFit = comp.fit === "scaleDown" ? "scale-down" : comp.fit;
                }
                return img;
            }

            case "Video": {
                const url = String(resolveValue(surface, comp.url, ""));
                if (!isSafeMediaUrl(url)) {
                    const fallback = document.createElement("div");
                    fallback.className = "a2ui-text variant-caption";
                    fallback.textContent = "[Blocked or invalid video URL]";
                    return fallback;
                }
                const video = document.createElement("video");
                video.className = "a2ui-video";
                video.controls = true;
                video.preload = "metadata";
                video.src = url;
                if (comp.posterUrl && isSafeMediaUrl(String(comp.posterUrl))) {
                    video.poster = String(comp.posterUrl);
                }
                return video;
            }

            case "AudioPlayer": {
                const url = String(resolveValue(surface, comp.url, ""));
                const box = document.createElement("div");
                box.className = "a2ui-audio-box";
                const desc = resolveValue(surface, comp.description, "");
                if (desc) {
                    const label = document.createElement("small");
                    label.textContent = String(desc);
                    box.appendChild(label);
                }
                if (!isSafeMediaUrl(url)) {
                    const fallback = document.createElement("span");
                    fallback.className = "a2ui-text variant-caption";
                    fallback.textContent = "[Blocked or invalid audio URL]";
                    box.appendChild(fallback);
                    return box;
                }
                const audio = document.createElement("audio");
                audio.className = "a2ui-audio";
                audio.controls = true;
                audio.preload = "metadata";
                audio.src = url;
                box.appendChild(audio);
                return box;
            }

            case "Button": {
                const btn = document.createElement("button");
                btn.type = "button";
                const variant = comp.variant || "default";
                btn.className = `a2ui-btn variant-${variant}`;
                if (comp.child) {
                    btn.appendChild(renderComponent(surface, comp.child, onAction, nextVisited));
                } else {
                    btn.textContent = String(resolveValue(surface, comp.label || comp.text, "Button"));
                }
                btn.addEventListener("click", () => {
                    const rawAction = comp.action || {};
                    const evt = rawAction.event || rawAction;
                    const actionName = evt.name || "button_click";
                    const context = resolveContextObject(surface, evt.context || {});
                    onAction({
                        name: actionName,
                        surface_id: surface.surfaceId,
                        source_component_id: componentId,
                        context,
                    });
                });
                return btn;
            }

            case "TextField": {
                const field = document.createElement("div");
                field.className = "a2ui-field";
                const labelText = resolveValue(surface, comp.label, "");
                if (labelText) {
                    const label = document.createElement("label");
                    label.className = "a2ui-field-label";
                    label.textContent = String(labelText);
                    field.appendChild(label);
                }
                const variant = comp.variant || "shortText";
                const bindingPath = getBindingPath(comp.value);
                const initialVal = String(resolveValue(surface, comp.value, ""));
                const input = document.createElement(variant === "longText" ? "textarea" : "input");
                if (variant === "longText") {
                    input.className = "a2ui-textarea";
                    input.rows = 3;
                } else {
                    input.className = "a2ui-input";
                    input.type =
                        variant === "obscured"
                            ? "password"
                            : variant === "number"
                              ? "number"
                              : "text";
                }
                input.value = initialVal;
                if (comp.placeholder) {
                    input.placeholder = String(resolveValue(surface, comp.placeholder, ""));
                }
                input.addEventListener("input", () => {
                    if (bindingPath) {
                        const val = variant === "number" && input.value !== "" ? Number(input.value) : input.value;
                        setByPointer(surface.dataModel, bindingPath, val);
                    }
                });
                field.appendChild(input);
                return field;
            }

            case "CheckBox": {
                const label = document.createElement("label");
                label.className = "a2ui-checkbox-label";
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                const bindingPath = getBindingPath(comp.value);
                checkbox.checked = Boolean(resolveValue(surface, comp.value, false));
                checkbox.addEventListener("change", () => {
                    if (bindingPath) {
                        setByPointer(surface.dataModel, bindingPath, checkbox.checked);
                    }
                });
                const span = document.createElement("span");
                span.textContent = String(resolveValue(surface, comp.label, "Option"));
                label.appendChild(checkbox);
                label.appendChild(span);
                return label;
            }

            case "ChoicePicker": {
                const field = document.createElement("div");
                field.className = "a2ui-field";
                const labelText = resolveValue(surface, comp.label, "");
                if (labelText) {
                    const label = document.createElement("label");
                    label.className = "a2ui-field-label";
                    label.textContent = String(labelText);
                    field.appendChild(label);
                }

                const options = Array.isArray(comp.options) ? comp.options : [];
                const isMulti = comp.variant === "multipleSelection";
                const displayStyle = comp.displayStyle || "checkbox";
                const bindingPath = getBindingPath(comp.value);
                let currentVal = resolveValue(surface, comp.value, isMulti ? [] : []);
                let selectedSet = new Set(
                    Array.isArray(currentVal)
                        ? currentVal.map(String)
                        : currentVal
                          ? [String(currentVal)]
                          : []
                );

                const optionsContainer = document.createElement("div");
                optionsContainer.className =
                    displayStyle === "chips" ? "a2ui-choice-options" : "a2ui-choice-options vertical";

                const syncSelection = () => {
                    if (bindingPath) {
                        setByPointer(surface.dataModel, bindingPath, Array.from(selectedSet));
                    }
                    Array.from(optionsContainer.children).forEach((chipEl) => {
                        const val = chipEl.dataset.value;
                        chipEl.classList.toggle("selected", selectedSet.has(val));
                    });
                };

                options.forEach((opt) => {
                    const optValue = String(opt.value ?? opt.label ?? "");
                    const optLabel = String(resolveValue(surface, opt.label, optValue));

                    const itemLabel = document.createElement("label");
                    itemLabel.className = "a2ui-choice-chip";
                    itemLabel.dataset.value = optValue;

                    const input = document.createElement("input");
                    input.type = isMulti ? "checkbox" : "radio";
                    input.name = `choice_${surface.surfaceId}_${componentId}`;
                    input.value = optValue;
                    input.checked = selectedSet.has(optValue);

                    input.addEventListener("change", () => {
                        if (isMulti) {
                            if (input.checked) {
                                selectedSet.add(optValue);
                            } else {
                                selectedSet.delete(optValue);
                            }
                        } else {
                            selectedSet = new Set([optValue]);
                        }
                        syncSelection();
                    });

                    const span = document.createElement("span");
                    span.textContent = optLabel;

                    itemLabel.appendChild(input);
                    itemLabel.appendChild(span);
                    optionsContainer.appendChild(itemLabel);
                });

                syncSelection();
                field.appendChild(optionsContainer);
                return field;
            }

            case "Slider": {
                const field = document.createElement("div");
                field.className = "a2ui-field";
                const labelText = resolveValue(surface, comp.label, "");
                if (labelText) {
                    const label = document.createElement("label");
                    label.className = "a2ui-field-label";
                    label.textContent = String(labelText);
                    field.appendChild(label);
                }

                const sliderRow = document.createElement("div");
                sliderRow.className = "a2ui-slider-row";

                const range = document.createElement("input");
                range.type = "range";
                range.min = String(comp.min ?? 0);
                range.max = String(comp.max ?? 100);
                if (comp.steps) {
                    const span = Number(range.max) - Number(range.min);
                    if (span > 0) {
                        range.step = String(span / Number(comp.steps));
                    }
                }

                const bindingPath = getBindingPath(comp.value);
                const startVal = Number(resolveValue(surface, comp.value, range.min));
                range.value = String(startVal);

                const readout = document.createElement("span");
                readout.className = "a2ui-slider-value";
                readout.textContent = range.value;

                range.addEventListener("input", () => {
                    readout.textContent = range.value;
                    if (bindingPath) {
                        setByPointer(surface.dataModel, bindingPath, Number(range.value));
                    }
                });

                sliderRow.appendChild(range);
                sliderRow.appendChild(readout);
                field.appendChild(sliderRow);
                return field;
            }

            case "DateTimeInput": {
                const field = document.createElement("div");
                field.className = "a2ui-field";
                const labelText = resolveValue(surface, comp.label, "");
                if (labelText) {
                    const label = document.createElement("label");
                    label.className = "a2ui-field-label";
                    label.textContent = String(labelText);
                    field.appendChild(label);
                }

                const enableDate = comp.enableDate !== false;
                const enableTime = Boolean(comp.enableTime);
                const input = document.createElement("input");
                input.className = "a2ui-input";

                if (enableDate && enableTime) {
                    input.type = "datetime-local";
                } else if (enableTime) {
                    input.type = "time";
                } else {
                    input.type = "date";
                }

                const bindingPath = getBindingPath(comp.value);
                const rawVal = String(resolveValue(surface, comp.value, ""));
                if (rawVal) {
                    if (input.type === "datetime-local") {
                        input.value = rawVal.slice(0, 16);
                    } else if (input.type === "date") {
                        input.value = rawVal.slice(0, 10);
                    } else {
                        input.value = rawVal.slice(0, 5);
                    }
                }

                input.addEventListener("change", () => {
                    if (bindingPath) {
                        setByPointer(surface.dataModel, bindingPath, input.value);
                    }
                });

                field.appendChild(input);
                return field;
            }

            default: {
                const unknown = document.createElement("div");
                unknown.className = "a2ui-text variant-caption";
                unknown.textContent = `[Unsupported A2UI component: ${type}]`;
                return unknown;
            }
        }
    }

    function renderA2uiMessages(messages, onAction) {
        const container = document.createElement("div");
        container.className = "a2ui-surfaces-container";
        const surfaces = new Map();

        const getOrCreateSurface = (surfaceId) => {
            if (!surfaces.has(surfaceId)) {
                surfaces.set(surfaceId, {
                    surfaceId,
                    rootId: "root",
                    components: new Map(),
                    dataModel: {},
                });
            }
            return surfaces.get(surfaceId);
        };

        for (const msg of messages || []) {
            if (!msg || typeof msg !== "object") continue;

            if (msg.createSurface) {
                const cs = msg.createSurface;
                const s = getOrCreateSurface(cs.surfaceId || "main");
                if (cs.root) s.rootId = cs.root;
                if (cs.dataModel && typeof cs.dataModel === "object") {
                    Object.assign(s.dataModel, cs.dataModel);
                }
                if (Array.isArray(cs.components)) {
                    for (const comp of cs.components) {
                        if (comp && comp.id) s.components.set(comp.id, comp);
                    }
                }
            }

            if (msg.updateDataModel) {
                const udm = msg.updateDataModel;
                const s = getOrCreateSurface(udm.surfaceId || "main");
                const val = "value" in udm ? udm.value : udm.contents;
                setByPointer(s.dataModel, udm.path || "/", val);
            }

            if (msg.updateComponents) {
                const uc = msg.updateComponents;
                const s = getOrCreateSurface(uc.surfaceId || "main");
                const comps = Array.isArray(uc.components) ? uc.components : [];
                for (const comp of comps) {
                    if (comp && comp.id) s.components.set(comp.id, comp);
                }
            }

            if (msg.deleteSurface && msg.deleteSurface.surfaceId) {
                surfaces.delete(msg.deleteSurface.surfaceId);
            }
        }

        for (const surface of surfaces.values()) {
            const surfaceEl = document.createElement("div");
            surfaceEl.className = "a2ui-surface";
            const rootId = surface.components.has(surface.rootId)
                ? surface.rootId
                : surface.components.keys().next().value;
            if (rootId) {
                surfaceEl.appendChild(renderComponent(surface, rootId, onAction));
            }
            container.appendChild(surfaceEl);
        }

        return container;
    }

    window.OracleA2uiRenderer = {
        renderA2uiMessages,
    };
})();
