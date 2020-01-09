
(function(l, r) { if (l.getElementById('livereloadscript')) return; r = l.createElement('script'); r.async = 1; r.src = '//' + (window.location.host || 'localhost').split(':')[0] + ':35729/livereload.js?snipver=1'; r.id = 'livereloadscript'; l.head.appendChild(r) })(window.document);
var app = (function () {
    'use strict';

    function noop() { }
    function add_location(element, file, line, column, char) {
        element.__svelte_meta = {
            loc: { file, line, column, char }
        };
    }
    function run(fn) {
        return fn();
    }
    function blank_object() {
        return Object.create(null);
    }
    function run_all(fns) {
        fns.forEach(run);
    }
    function is_function(thing) {
        return typeof thing === 'function';
    }
    function safe_not_equal(a, b) {
        return a != a ? b == b : a !== b || ((a && typeof a === 'object') || typeof a === 'function');
    }
    function null_to_empty(value) {
        return value == null ? '' : value;
    }
    const has_prop = (obj, prop) => Object.prototype.hasOwnProperty.call(obj, prop);

    function append(target, node) {
        target.appendChild(node);
    }
    function insert(target, node, anchor) {
        target.insertBefore(node, anchor || null);
    }
    function detach(node) {
        node.parentNode.removeChild(node);
    }
    function destroy_each(iterations, detaching) {
        for (let i = 0; i < iterations.length; i += 1) {
            if (iterations[i])
                iterations[i].d(detaching);
        }
    }
    function element(name) {
        return document.createElement(name);
    }
    function text(data) {
        return document.createTextNode(data);
    }
    function space() {
        return text(' ');
    }
    function empty() {
        return text('');
    }
    function listen(node, event, handler, options) {
        node.addEventListener(event, handler, options);
        return () => node.removeEventListener(event, handler, options);
    }
    function attr(node, attribute, value) {
        if (value == null)
            node.removeAttribute(attribute);
        else if (node.getAttribute(attribute) !== value)
            node.setAttribute(attribute, value);
    }
    function children(element) {
        return Array.from(element.childNodes);
    }
    function custom_event(type, detail) {
        const e = document.createEvent('CustomEvent');
        e.initCustomEvent(type, false, false, detail);
        return e;
    }

    let current_component;
    function set_current_component(component) {
        current_component = component;
    }

    const dirty_components = [];
    const binding_callbacks = [];
    const render_callbacks = [];
    const flush_callbacks = [];
    const resolved_promise = Promise.resolve();
    let update_scheduled = false;
    function schedule_update() {
        if (!update_scheduled) {
            update_scheduled = true;
            resolved_promise.then(flush);
        }
    }
    function add_render_callback(fn) {
        render_callbacks.push(fn);
    }
    function add_flush_callback(fn) {
        flush_callbacks.push(fn);
    }
    function flush() {
        const seen_callbacks = new Set();
        do {
            // first, call beforeUpdate functions
            // and update components
            while (dirty_components.length) {
                const component = dirty_components.shift();
                set_current_component(component);
                update(component.$$);
            }
            while (binding_callbacks.length)
                binding_callbacks.pop()();
            // then, once components are updated, call
            // afterUpdate functions. This may cause
            // subsequent updates...
            for (let i = 0; i < render_callbacks.length; i += 1) {
                const callback = render_callbacks[i];
                if (!seen_callbacks.has(callback)) {
                    callback();
                    // ...so guard against infinite loops
                    seen_callbacks.add(callback);
                }
            }
            render_callbacks.length = 0;
        } while (dirty_components.length);
        while (flush_callbacks.length) {
            flush_callbacks.pop()();
        }
        update_scheduled = false;
    }
    function update($$) {
        if ($$.fragment !== null) {
            $$.update($$.dirty);
            run_all($$.before_update);
            $$.fragment && $$.fragment.p($$.dirty, $$.ctx);
            $$.dirty = null;
            $$.after_update.forEach(add_render_callback);
        }
    }
    const outroing = new Set();
    let outros;
    function group_outros() {
        outros = {
            r: 0,
            c: [],
            p: outros // parent group
        };
    }
    function check_outros() {
        if (!outros.r) {
            run_all(outros.c);
        }
        outros = outros.p;
    }
    function transition_in(block, local) {
        if (block && block.i) {
            outroing.delete(block);
            block.i(local);
        }
    }
    function transition_out(block, local, detach, callback) {
        if (block && block.o) {
            if (outroing.has(block))
                return;
            outroing.add(block);
            outros.c.push(() => {
                outroing.delete(block);
                if (callback) {
                    if (detach)
                        block.d(1);
                    callback();
                }
            });
            block.o(local);
        }
    }

    const globals = (typeof window !== 'undefined' ? window : global);

    function bind(component, name, callback) {
        if (has_prop(component.$$.props, name)) {
            name = component.$$.props[name] || name;
            component.$$.bound[name] = callback;
            callback(component.$$.ctx[name]);
        }
    }
    function create_component(block) {
        block && block.c();
    }
    function mount_component(component, target, anchor) {
        const { fragment, on_mount, on_destroy, after_update } = component.$$;
        fragment && fragment.m(target, anchor);
        // onMount happens before the initial afterUpdate
        add_render_callback(() => {
            const new_on_destroy = on_mount.map(run).filter(is_function);
            if (on_destroy) {
                on_destroy.push(...new_on_destroy);
            }
            else {
                // Edge case - component was destroyed immediately,
                // most likely as a result of a binding initialising
                run_all(new_on_destroy);
            }
            component.$$.on_mount = [];
        });
        after_update.forEach(add_render_callback);
    }
    function destroy_component(component, detaching) {
        const $$ = component.$$;
        if ($$.fragment !== null) {
            run_all($$.on_destroy);
            $$.fragment && $$.fragment.d(detaching);
            // TODO null out other refs, including component.$$ (but need to
            // preserve final state?)
            $$.on_destroy = $$.fragment = null;
            $$.ctx = {};
        }
    }
    function make_dirty(component, key) {
        if (!component.$$.dirty) {
            dirty_components.push(component);
            schedule_update();
            component.$$.dirty = blank_object();
        }
        component.$$.dirty[key] = true;
    }
    function init(component, options, instance, create_fragment, not_equal, props) {
        const parent_component = current_component;
        set_current_component(component);
        const prop_values = options.props || {};
        const $$ = component.$$ = {
            fragment: null,
            ctx: null,
            // state
            props,
            update: noop,
            not_equal,
            bound: blank_object(),
            // lifecycle
            on_mount: [],
            on_destroy: [],
            before_update: [],
            after_update: [],
            context: new Map(parent_component ? parent_component.$$.context : []),
            // everything else
            callbacks: blank_object(),
            dirty: null
        };
        let ready = false;
        $$.ctx = instance
            ? instance(component, prop_values, (key, ret, value = ret) => {
                if ($$.ctx && not_equal($$.ctx[key], $$.ctx[key] = value)) {
                    if ($$.bound[key])
                        $$.bound[key](value);
                    if (ready)
                        make_dirty(component, key);
                }
                return ret;
            })
            : prop_values;
        $$.update();
        ready = true;
        run_all($$.before_update);
        // `false` as a special case of no DOM component
        $$.fragment = create_fragment ? create_fragment($$.ctx) : false;
        if (options.target) {
            if (options.hydrate) {
                // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
                $$.fragment && $$.fragment.l(children(options.target));
            }
            else {
                // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
                $$.fragment && $$.fragment.c();
            }
            if (options.intro)
                transition_in(component.$$.fragment);
            mount_component(component, options.target, options.anchor);
            flush();
        }
        set_current_component(parent_component);
    }
    class SvelteComponent {
        $destroy() {
            destroy_component(this, 1);
            this.$destroy = noop;
        }
        $on(type, callback) {
            const callbacks = (this.$$.callbacks[type] || (this.$$.callbacks[type] = []));
            callbacks.push(callback);
            return () => {
                const index = callbacks.indexOf(callback);
                if (index !== -1)
                    callbacks.splice(index, 1);
            };
        }
        $set() {
            // overridden by instance, if it has props
        }
    }

    function dispatch_dev(type, detail) {
        document.dispatchEvent(custom_event(type, detail));
    }
    function append_dev(target, node) {
        dispatch_dev("SvelteDOMInsert", { target, node });
        append(target, node);
    }
    function insert_dev(target, node, anchor) {
        dispatch_dev("SvelteDOMInsert", { target, node, anchor });
        insert(target, node, anchor);
    }
    function detach_dev(node) {
        dispatch_dev("SvelteDOMRemove", { node });
        detach(node);
    }
    function listen_dev(node, event, handler, options, has_prevent_default, has_stop_propagation) {
        const modifiers = options === true ? ["capture"] : options ? Array.from(Object.keys(options)) : [];
        if (has_prevent_default)
            modifiers.push('preventDefault');
        if (has_stop_propagation)
            modifiers.push('stopPropagation');
        dispatch_dev("SvelteDOMAddEventListener", { node, event, handler, modifiers });
        const dispose = listen(node, event, handler, options);
        return () => {
            dispatch_dev("SvelteDOMRemoveEventListener", { node, event, handler, modifiers });
            dispose();
        };
    }
    function attr_dev(node, attribute, value) {
        attr(node, attribute, value);
        if (value == null)
            dispatch_dev("SvelteDOMRemoveAttribute", { node, attribute });
        else
            dispatch_dev("SvelteDOMSetAttribute", { node, attribute, value });
    }
    class SvelteComponentDev extends SvelteComponent {
        constructor(options) {
            if (!options || (!options.target && !options.$$inline)) {
                throw new Error(`'target' is a required option`);
            }
            super();
        }
        $destroy() {
            super.$destroy();
            this.$destroy = () => {
                console.warn(`Component was already destroyed`); // eslint-disable-line no-console
            };
        }
    }

    /* src/Instrument.svelte generated by Svelte v3.13.0 */

    const file = "src/Instrument.svelte";

    function create_fragment(ctx) {
    	let div6;
    	let h50;
    	let t1;
    	let div0;
    	let div0_id_value;
    	let t2;
    	let hr0;
    	let t3;
    	let h51;
    	let t5;
    	let div1;
    	let div1_id_value;
    	let t6;
    	let hr1;
    	let t7;
    	let h52;
    	let t9;
    	let div2;
    	let div2_id_value;
    	let t10;
    	let hr2;
    	let t11;
    	let h53;
    	let t13;
    	let div3;
    	let div3_id_value;
    	let t14;
    	let hr3;
    	let t15;
    	let h54;
    	let t17;
    	let div4;
    	let div4_id_value;
    	let t18;
    	let hr4;
    	let t19;
    	let h55;
    	let t21;
    	let div5;
    	let div5_id_value;
    	let t22;
    	let hr5;

    	const block = {
    		c: function create() {
    			div6 = element("div");
    			h50 = element("h5");
    			h50.textContent = "# Identifications";
    			t1 = space();
    			div0 = element("div");
    			t2 = space();
    			hr0 = element("hr");
    			t3 = space();
    			h51 = element("h5");
    			h51.textContent = "# PSMs";
    			t5 = space();
    			div1 = element("div");
    			t6 = space();
    			hr1 = element("hr");
    			t7 = space();
    			h52 = element("h5");
    			h52.textContent = "Peptide precursor areas";
    			t9 = space();
    			div2 = element("div");
    			t10 = space();
    			hr2 = element("hr");
    			t11 = space();
    			h53 = element("h5");
    			h53.textContent = "PSM MSGFScore";
    			t13 = space();
    			div3 = element("div");
    			t14 = space();
    			hr3 = element("hr");
    			t15 = space();
    			h54 = element("h5");
    			h54.textContent = "Precursor error (ppm)";
    			t17 = space();
    			div4 = element("div");
    			t18 = space();
    			hr4 = element("hr");
    			t19 = space();
    			h55 = element("h5");
    			h55.textContent = "Retention time (min)";
    			t21 = space();
    			div5 = element("div");
    			t22 = space();
    			hr5 = element("hr");
    			attr_dev(h50, "class", "title is-5");
    			add_location(h50, file, 5, 2, 67);
    			attr_dev(div0, "class", "bk-plotdiv");
    			attr_dev(div0, "id", div0_id_value = ctx.bokeh_code.div.amount_peptides.elementid);
    			add_location(div0, file, 6, 2, 115);
    			add_location(hr0, file, 7, 2, 194);
    			attr_dev(h51, "class", "title is-5");
    			add_location(h51, file, 8, 2, 201);
    			attr_dev(div1, "class", "bk-plotdiv");
    			attr_dev(div1, "id", div1_id_value = ctx.bokeh_code.div.amount_psms.elementid);
    			add_location(div1, file, 9, 2, 238);
    			add_location(hr1, file, 10, 2, 313);
    			attr_dev(h52, "class", "title is-5");
    			add_location(h52, file, 11, 2, 320);
    			attr_dev(div2, "class", "bk-plotdiv");
    			attr_dev(div2, "id", div2_id_value = ctx.bokeh_code.div.precursorarea.elementid);
    			add_location(div2, file, 12, 2, 374);
    			add_location(hr2, file, 13, 2, 451);
    			attr_dev(h53, "class", "title is-5");
    			add_location(h53, file, 14, 2, 458);
    			attr_dev(div3, "class", "bk-plotdiv");
    			attr_dev(div3, "id", div3_id_value = ctx.bokeh_code.div.msgfscore.elementid);
    			add_location(div3, file, 15, 2, 502);
    			add_location(hr3, file, 16, 2, 575);
    			attr_dev(h54, "class", "title is-5");
    			add_location(h54, file, 17, 2, 582);
    			attr_dev(div4, "class", "bk-plotdiv");
    			attr_dev(div4, "id", div4_id_value = ctx.bokeh_code.div.prec_error.elementid);
    			add_location(div4, file, 18, 2, 634);
    			add_location(hr4, file, 19, 2, 708);
    			attr_dev(h55, "class", "title is-5");
    			add_location(h55, file, 20, 2, 715);
    			attr_dev(div5, "class", "bk-plotdiv");
    			attr_dev(div5, "id", div5_id_value = ctx.bokeh_code.div.rt.elementid);
    			add_location(div5, file, 21, 2, 766);
    			add_location(hr5, file, 22, 2, 832);
    			attr_dev(div6, "class", "bk-root");
    			add_location(div6, file, 4, 0, 43);
    		},
    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div6, anchor);
    			append_dev(div6, h50);
    			append_dev(div6, t1);
    			append_dev(div6, div0);
    			append_dev(div6, t2);
    			append_dev(div6, hr0);
    			append_dev(div6, t3);
    			append_dev(div6, h51);
    			append_dev(div6, t5);
    			append_dev(div6, div1);
    			append_dev(div6, t6);
    			append_dev(div6, hr1);
    			append_dev(div6, t7);
    			append_dev(div6, h52);
    			append_dev(div6, t9);
    			append_dev(div6, div2);
    			append_dev(div6, t10);
    			append_dev(div6, hr2);
    			append_dev(div6, t11);
    			append_dev(div6, h53);
    			append_dev(div6, t13);
    			append_dev(div6, div3);
    			append_dev(div6, t14);
    			append_dev(div6, hr3);
    			append_dev(div6, t15);
    			append_dev(div6, h54);
    			append_dev(div6, t17);
    			append_dev(div6, div4);
    			append_dev(div6, t18);
    			append_dev(div6, hr4);
    			append_dev(div6, t19);
    			append_dev(div6, h55);
    			append_dev(div6, t21);
    			append_dev(div6, div5);
    			append_dev(div6, t22);
    			append_dev(div6, hr5);
    		},
    		p: function update(changed, ctx) {
    			if (changed.bokeh_code && div0_id_value !== (div0_id_value = ctx.bokeh_code.div.amount_peptides.elementid)) {
    				attr_dev(div0, "id", div0_id_value);
    			}

    			if (changed.bokeh_code && div1_id_value !== (div1_id_value = ctx.bokeh_code.div.amount_psms.elementid)) {
    				attr_dev(div1, "id", div1_id_value);
    			}

    			if (changed.bokeh_code && div2_id_value !== (div2_id_value = ctx.bokeh_code.div.precursorarea.elementid)) {
    				attr_dev(div2, "id", div2_id_value);
    			}

    			if (changed.bokeh_code && div3_id_value !== (div3_id_value = ctx.bokeh_code.div.msgfscore.elementid)) {
    				attr_dev(div3, "id", div3_id_value);
    			}

    			if (changed.bokeh_code && div4_id_value !== (div4_id_value = ctx.bokeh_code.div.prec_error.elementid)) {
    				attr_dev(div4, "id", div4_id_value);
    			}

    			if (changed.bokeh_code && div5_id_value !== (div5_id_value = ctx.bokeh_code.div.rt.elementid)) {
    				attr_dev(div5, "id", div5_id_value);
    			}
    		},
    		i: noop,
    		o: noop,
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div6);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_fragment.name,
    		type: "component",
    		source: "",
    		ctx
    	});

    	return block;
    }

    function instance($$self, $$props, $$invalidate) {
    	let { bokeh_code } = $$props;
    	const writable_props = ["bokeh_code"];

    	Object.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith("$$")) console.warn(`<Instrument> was created with unknown prop '${key}'`);
    	});

    	$$self.$set = $$props => {
    		if ("bokeh_code" in $$props) $$invalidate("bokeh_code", bokeh_code = $$props.bokeh_code);
    	};

    	$$self.$capture_state = () => {
    		return { bokeh_code };
    	};

    	$$self.$inject_state = $$props => {
    		if ("bokeh_code" in $$props) $$invalidate("bokeh_code", bokeh_code = $$props.bokeh_code);
    	};

    	return { bokeh_code };
    }

    class Instrument extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance, create_fragment, safe_not_equal, { bokeh_code: 0 });

    		dispatch_dev("SvelteRegisterComponent", {
    			component: this,
    			tagName: "Instrument",
    			options,
    			id: create_fragment.name
    		});

    		const { ctx } = this.$$;
    		const props = options.props || ({});

    		if (ctx.bokeh_code === undefined && !("bokeh_code" in props)) {
    			console.warn("<Instrument> was created without expected prop 'bokeh_code'");
    		}
    	}

    	get bokeh_code() {
    		throw new Error("<Instrument>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set bokeh_code(value) {
    		throw new Error("<Instrument>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/App.svelte generated by Svelte v3.13.0 */

    const { Object: Object_1 } = globals;
    const file$1 = "src/App.svelte";

    function get_each_context(ctx, list, i) {
    	const child_ctx = Object_1.create(ctx);
    	child_ctx.instr = list[i];
    	return child_ctx;
    }

    function get_each_context_1(ctx, list, i) {
    	const child_ctx = Object_1.create(ctx);
    	child_ctx.instr = list[i];
    	return child_ctx;
    }

    // (55:4) {#each instruments as instr}
    function create_each_block_1(ctx) {
    	let li;
    	let a;
    	let span;
    	let t0_value = ctx.instr[0] + "";
    	let t0;
    	let t1;
    	let li_class_value;
    	let dispose;

    	function click_handler(...args) {
    		return ctx.click_handler(ctx, ...args);
    	}

    	const block = {
    		c: function create() {
    			li = element("li");
    			a = element("a");
    			span = element("span");
    			t0 = text(t0_value);
    			t1 = space();
    			add_location(span, file$1, 56, 44, 1310);
    			add_location(a, file$1, 56, 6, 1272);

    			attr_dev(li, "class", li_class_value = ctx.tabshow === `instr_${ctx.instr[1]}`
    			? "is-active"
    			: "");

    			add_location(li, file$1, 55, 4, 1201);
    			dispose = listen_dev(a, "click", click_handler, false, false, false);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, li, anchor);
    			append_dev(li, a);
    			append_dev(a, span);
    			append_dev(span, t0);
    			append_dev(li, t1);
    		},
    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;

    			if (changed.tabshow && li_class_value !== (li_class_value = ctx.tabshow === `instr_${ctx.instr[1]}`
    			? "is-active"
    			: "")) {
    				attr_dev(li, "class", li_class_value);
    			}
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(li);
    			dispose();
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_each_block_1.name,
    		type: "each",
    		source: "(55:4) {#each instruments as instr}",
    		ctx
    	});

    	return block;
    }

    // (67:4) {#if qcdata[instr[1]].loaded}
    function create_if_block(ctx) {
    	let div;
    	let updating_bokeh_code;
    	let t;
    	let div_class_value;
    	let current;

    	function instrument_bokeh_code_binding(value) {
    		ctx.instrument_bokeh_code_binding.call(null, value, ctx);
    		updating_bokeh_code = true;
    		add_flush_callback(() => updating_bokeh_code = false);
    	}

    	let instrument_props = {};

    	if (ctx.qcdata[ctx.instr[1]].bokeh_code !== void 0) {
    		instrument_props.bokeh_code = ctx.qcdata[ctx.instr[1]].bokeh_code;
    	}

    	const instrument = new Instrument({ props: instrument_props, $$inline: true });
    	binding_callbacks.push(() => bind(instrument, "bokeh_code", instrument_bokeh_code_binding));

    	const block = {
    		c: function create() {
    			div = element("div");
    			create_component(instrument.$$.fragment);
    			t = space();

    			attr_dev(div, "class", div_class_value = "" + (null_to_empty(`instrplot ${ctx.tabshow === `instr_${ctx.instr[1]}`
			? "active"
			: "inactive"}`) + " svelte-sub9ii"));

    			add_location(div, file$1, 67, 4, 1555);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			mount_component(instrument, div, null);
    			append_dev(div, t);
    			current = true;
    		},
    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			const instrument_changes = {};

    			if (!updating_bokeh_code && (changed.qcdata || changed.instruments)) {
    				instrument_changes.bokeh_code = ctx.qcdata[ctx.instr[1]].bokeh_code;
    			}

    			instrument.$set(instrument_changes);

    			if (!current || changed.tabshow && div_class_value !== (div_class_value = "" + (null_to_empty(`instrplot ${ctx.tabshow === `instr_${ctx.instr[1]}`
			? "active"
			: "inactive"}`) + " svelte-sub9ii"))) {
    				attr_dev(div, "class", div_class_value);
    			}
    		},
    		i: function intro(local) {
    			if (current) return;
    			transition_in(instrument.$$.fragment, local);
    			current = true;
    		},
    		o: function outro(local) {
    			transition_out(instrument.$$.fragment, local);
    			current = false;
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div);
    			destroy_component(instrument);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_if_block.name,
    		type: "if",
    		source: "(67:4) {#if qcdata[instr[1]].loaded}",
    		ctx
    	});

    	return block;
    }

    // (66:4) {#each instruments as instr}
    function create_each_block(ctx) {
    	let if_block_anchor;
    	let current;
    	let if_block = ctx.qcdata[ctx.instr[1]].loaded && create_if_block(ctx);

    	const block = {
    		c: function create() {
    			if (if_block) if_block.c();
    			if_block_anchor = empty();
    		},
    		m: function mount(target, anchor) {
    			if (if_block) if_block.m(target, anchor);
    			insert_dev(target, if_block_anchor, anchor);
    			current = true;
    		},
    		p: function update(changed, ctx) {
    			if (ctx.qcdata[ctx.instr[1]].loaded) {
    				if (if_block) {
    					if_block.p(changed, ctx);
    					transition_in(if_block, 1);
    				} else {
    					if_block = create_if_block(ctx);
    					if_block.c();
    					transition_in(if_block, 1);
    					if_block.m(if_block_anchor.parentNode, if_block_anchor);
    				}
    			} else if (if_block) {
    				group_outros();

    				transition_out(if_block, 1, 1, () => {
    					if_block = null;
    				});

    				check_outros();
    			}
    		},
    		i: function intro(local) {
    			if (current) return;
    			transition_in(if_block);
    			current = true;
    		},
    		o: function outro(local) {
    			transition_out(if_block);
    			current = false;
    		},
    		d: function destroy(detaching) {
    			if (if_block) if_block.d(detaching);
    			if (detaching) detach_dev(if_block_anchor);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_each_block.name,
    		type: "each",
    		source: "(66:4) {#each instruments as instr}",
    		ctx
    	});

    	return block;
    }

    function create_fragment$1(ctx) {
    	let div0;
    	let ul;
    	let t0;
    	let div1;
    	let a;
    	let t2;
    	let hr;
    	let t3;
    	let section;
    	let current;
    	let dispose;
    	let each_value_1 = instruments;
    	let each_blocks_1 = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks_1[i] = create_each_block_1(get_each_context_1(ctx, each_value_1, i));
    	}

    	let each_value = instruments;
    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block(get_each_context(ctx, each_value, i));
    	}

    	const out = i => transition_out(each_blocks[i], 1, 1, () => {
    		each_blocks[i] = null;
    	});

    	const block = {
    		c: function create() {
    			div0 = element("div");
    			ul = element("ul");

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].c();
    			}

    			t0 = space();
    			div1 = element("div");
    			a = element("a");
    			a.textContent = "Refresh";
    			t2 = space();
    			hr = element("hr");
    			t3 = space();
    			section = element("section");

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			add_location(ul, file$1, 48, 1, 1020);
    			attr_dev(div0, "class", "tabs is-toggle is-centered is-small");
    			add_location(div0, file$1, 47, 0, 969);
    			attr_dev(a, "class", "button is-info is-small");
    			add_location(a, file$1, 62, 2, 1400);
    			add_location(hr, file$1, 63, 2, 1467);
    			add_location(section, file$1, 64, 2, 1474);
    			attr_dev(div1, "class", "container");
    			add_location(div1, file$1, 61, 0, 1374);
    			dispose = listen_dev(a, "click", ctx.reload, false, false, false);
    		},
    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div0, anchor);
    			append_dev(div0, ul);

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].m(ul, null);
    			}

    			insert_dev(target, t0, anchor);
    			insert_dev(target, div1, anchor);
    			append_dev(div1, a);
    			append_dev(div1, t2);
    			append_dev(div1, hr);
    			append_dev(div1, t3);
    			append_dev(div1, section);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(section, null);
    			}

    			current = true;
    		},
    		p: function update(changed, ctx) {
    			if (changed.tabshow || changed.instruments || changed.showInst) {
    				each_value_1 = instruments;
    				let i;

    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1(ctx, each_value_1, i);

    					if (each_blocks_1[i]) {
    						each_blocks_1[i].p(changed, child_ctx);
    					} else {
    						each_blocks_1[i] = create_each_block_1(child_ctx);
    						each_blocks_1[i].c();
    						each_blocks_1[i].m(ul, null);
    					}
    				}

    				for (; i < each_blocks_1.length; i += 1) {
    					each_blocks_1[i].d(1);
    				}

    				each_blocks_1.length = each_value_1.length;
    			}

    			if (changed.qcdata || changed.instruments || changed.tabshow) {
    				each_value = instruments;
    				let i;

    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    						transition_in(each_blocks[i], 1);
    					} else {
    						each_blocks[i] = create_each_block(child_ctx);
    						each_blocks[i].c();
    						transition_in(each_blocks[i], 1);
    						each_blocks[i].m(section, null);
    					}
    				}

    				group_outros();

    				for (i = each_value.length; i < each_blocks.length; i += 1) {
    					out(i);
    				}

    				check_outros();
    			}
    		},
    		i: function intro(local) {
    			if (current) return;

    			for (let i = 0; i < each_value.length; i += 1) {
    				transition_in(each_blocks[i]);
    			}

    			current = true;
    		},
    		o: function outro(local) {
    			each_blocks = each_blocks.filter(Boolean);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				transition_out(each_blocks[i]);
    			}

    			current = false;
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div0);
    			destroy_each(each_blocks_1, detaching);
    			if (detaching) detach_dev(t0);
    			if (detaching) detach_dev(div1);
    			destroy_each(each_blocks, detaching);
    			dispose();
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_fragment$1.name,
    		type: "component",
    		source: "",
    		ctx
    	});

    	return block;
    }

    function instance$1($$self, $$props, $$invalidate) {
    	let tabshow = "dash";
    	let qcdata = Object.fromEntries(instruments.map(x => [x[1], { loaded: false }]));

    	async function showInst(iid) {
    		if (!qcdata[iid].loaded) {
    			await getInstrumentQC(iid);
    			eval(qcdata[iid].bokeh_code.script);
    		}

    		$$invalidate("tabshow", tabshow = `instr_${iid}`);
    	}

    	async function reload() {
    		if (tabshow.slice(0, 6) === "instr_") {
    			const iid = tabshow.substr(6);
    			$$invalidate("qcdata", qcdata[iid].loaded = false, qcdata);
    			await getInstrumentQC(iid);
    			eval(qcdata[iid].bokeh_code.script);
    		}
    	}

    	async function getInstrumentQC(instr_id) {
    		const response = await fetch("/dash/longqc/" + instr_id);
    		const result = await response.json();
    		$$invalidate("qcdata", qcdata[instr_id] = {}, qcdata);

    		for (let key in result) {
    			$$invalidate("qcdata", qcdata[instr_id][key] = result[key], qcdata);
    		}

    		$$invalidate("qcdata", qcdata[instr_id].loaded = true, qcdata);
    	}

    	const click_handler = ({ instr }, e) => showInst(instr[1]);

    	function instrument_bokeh_code_binding(value, { instr }) {
    		qcdata[instr[1]].bokeh_code = value;
    		$$invalidate("qcdata", qcdata);
    	}

    	$$self.$capture_state = () => {
    		return {};
    	};

    	$$self.$inject_state = $$props => {
    		if ("tabshow" in $$props) $$invalidate("tabshow", tabshow = $$props.tabshow);
    		if ("qcdata" in $$props) $$invalidate("qcdata", qcdata = $$props.qcdata);
    	};

    	return {
    		tabshow,
    		qcdata,
    		showInst,
    		reload,
    		click_handler,
    		instrument_bokeh_code_binding
    	};
    }

    class App extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$1, create_fragment$1, safe_not_equal, {});

    		dispatch_dev("SvelteRegisterComponent", {
    			component: this,
    			tagName: "App",
    			options,
    			id: create_fragment$1.name
    		});
    	}
    }

    var app = new App({
    	target: document.querySelector('#apps')
    });

    return app;

}());
//# sourceMappingURL=bundle.js.map
