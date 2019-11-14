
(function(l, r) { if (l.getElementById('livereloadscript')) return; r = l.createElement('script'); r.async = 1; r.src = '//' + (window.location.host || 'localhost').split(':')[0] + ':35729/livereload.js?snipver=1'; r.id = 'livereloadscript'; l.head.appendChild(r) })(document);
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
    function validate_store(store, name) {
        if (!store || typeof store.subscribe !== 'function') {
            throw new Error(`'${name}' is not a store with a 'subscribe' method`);
        }
    }
    function subscribe(store, callback) {
        const unsub = store.subscribe(callback);
        return unsub.unsubscribe ? () => unsub.unsubscribe() : unsub;
    }
    function component_subscribe(component, store, callback) {
        component.$$.on_destroy.push(subscribe(store, callback));
    }
    function null_to_empty(value) {
        return value == null ? '' : value;
    }
    function set_store_value(store, ret, value = ret) {
        store.set(value);
        return ret;
    }

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
        else
            node.setAttribute(attribute, value);
    }
    function to_number(value) {
        return value === '' ? undefined : +value;
    }
    function children(element) {
        return Array.from(element.childNodes);
    }
    function set_input_value(input, value) {
        if (value != null || input.value) {
            input.value = value;
        }
    }
    function set_style(node, key, value, important) {
        node.style.setProperty(key, value, important ? 'important' : '');
    }
    function select_option(select, value) {
        for (let i = 0; i < select.options.length; i += 1) {
            const option = select.options[i];
            if (option.__value === value) {
                option.selected = true;
                return;
            }
        }
    }
    function select_value(select) {
        const selected_option = select.querySelector(':checked') || select.options[0];
        return selected_option && selected_option.__value;
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
    function get_current_component() {
        if (!current_component)
            throw new Error(`Function called outside component initialization`);
        return current_component;
    }
    function onMount(fn) {
        get_current_component().$$.on_mount.push(fn);
    }
    function createEventDispatcher() {
        const component = current_component;
        return (type, detail) => {
            const callbacks = component.$$.callbacks[type];
            if (callbacks) {
                // TODO are there situations where events could be dispatched
                // in a server (non-DOM) environment?
                const event = custom_event(type, detail);
                callbacks.slice().forEach(fn => {
                    fn.call(component, event);
                });
            }
        };
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
        if ($$.fragment) {
            $$.update($$.dirty);
            run_all($$.before_update);
            $$.fragment.p($$.dirty, $$.ctx);
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
        if (component.$$.props.indexOf(name) === -1)
            return;
        component.$$.bound[name] = callback;
        callback(component.$$.ctx[name]);
    }
    function mount_component(component, target, anchor) {
        const { fragment, on_mount, on_destroy, after_update } = component.$$;
        fragment.m(target, anchor);
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
        if (component.$$.fragment) {
            run_all(component.$$.on_destroy);
            component.$$.fragment.d(detaching);
            // TODO null out other refs, including component.$$ (but need to
            // preserve final state?)
            component.$$.on_destroy = component.$$.fragment = null;
            component.$$.ctx = {};
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
    function init(component, options, instance, create_fragment, not_equal, prop_names) {
        const parent_component = current_component;
        set_current_component(component);
        const props = options.props || {};
        const $$ = component.$$ = {
            fragment: null,
            ctx: null,
            // state
            props: prop_names,
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
            ? instance(component, props, (key, ret, value = ret) => {
                if ($$.ctx && not_equal($$.ctx[key], $$.ctx[key] = value)) {
                    if ($$.bound[key])
                        $$.bound[key](value);
                    if (ready)
                        make_dirty(component, key);
                }
                return ret;
            })
            : props;
        $$.update();
        ready = true;
        run_all($$.before_update);
        $$.fragment = create_fragment($$.ctx);
        if (options.target) {
            if (options.hydrate) {
                // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
                $$.fragment.l(children(options.target));
            }
            else {
                // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
                $$.fragment.c();
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
    function prop_dev(node, property, value) {
        node[property] = value;
        dispatch_dev("SvelteDOMSetProperty", { node, property, value });
    }
    function set_data_dev(text, data) {
        data = '' + data;
        if (text.data === data)
            return;
        dispatch_dev("SvelteDOMSetData", { node: text, data });
        text.data = data;
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

    async function getJSON(url) {
      const response = await fetch(url);
      return await response.json();
    }

    async function postJSON(url, postdata) {
      const response = await fetch(url, {
        method: 'POST', headers: {
          'Content-Type': 'application/json'
        }, body: JSON.stringify(postdata)
      });
      try {
          return await response.json()
      } catch(error) {
          throw new Error(response.status);
      }
    }

    const subscriber_queue = [];
    /**
     * Create a `Writable` store that allows both updating and reading by subscription.
     * @param {*=}value initial value
     * @param {StartStopNotifier=}start start and stop notifications for subscriptions
     */
    function writable(value, start = noop) {
        let stop;
        const subscribers = [];
        function set(new_value) {
            if (safe_not_equal(value, new_value)) {
                value = new_value;
                if (stop) { // store is ready
                    const run_queue = !subscriber_queue.length;
                    for (let i = 0; i < subscribers.length; i += 1) {
                        const s = subscribers[i];
                        s[1]();
                        subscriber_queue.push(s, value);
                    }
                    if (run_queue) {
                        for (let i = 0; i < subscriber_queue.length; i += 2) {
                            subscriber_queue[i][0](subscriber_queue[i + 1]);
                        }
                        subscriber_queue.length = 0;
                    }
                }
            }
        }
        function update(fn) {
            set(fn(value));
        }
        function subscribe(run, invalidate = noop) {
            const subscriber = [run, invalidate];
            subscribers.push(subscriber);
            if (subscribers.length === 1) {
                stop = start(set) || noop;
            }
            run(value);
            return () => {
                const index = subscribers.indexOf(subscriber);
                if (index !== -1) {
                    subscribers.splice(index, 1);
                }
                if (subscribers.length === 0) {
                    stop();
                    stop = null;
                }
            };
        }
        return { set, update, subscribe };
    }

    const dataset_id = writable(false);

    const datasetFiles = writable({});

    const projsamples = writable({});

    /* src/Param.svelte generated by Svelte v3.12.1 */

    const file = "src/Param.svelte";

    function get_each_context_1(ctx, list, i) {
    	const child_ctx = Object.create(ctx);
    	child_ctx.option = list[i];
    	child_ctx.each_value_1 = list;
    	child_ctx.option_index_1 = i;
    	return child_ctx;
    }

    function get_each_context(ctx, list, i) {
    	const child_ctx = Object.create(ctx);
    	child_ctx.option = list[i];
    	return child_ctx;
    }

    // (27:45) 
    function create_if_block_3(ctx) {
    	var each_1_anchor;

    	let each_value_1 = ctx.param.fields;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks[i] = create_each_block_1(get_each_context_1(ctx, each_value_1, i));
    	}

    	const block = {
    		c: function create() {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			each_1_anchor = empty();
    		},

    		m: function mount(target, anchor) {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(target, anchor);
    			}

    			insert_dev(target, each_1_anchor, anchor);
    		},

    		p: function update(changed, ctx) {
    			if (changed.param) {
    				each_value_1 = ctx.param.fields;

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1(ctx, each_value_1, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_1(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(each_1_anchor.parentNode, each_1_anchor);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_1.length;
    			}
    		},

    		d: function destroy(detaching) {
    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(each_1_anchor);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_3.name, type: "if", source: "(27:45) ", ctx });
    	return block;
    }

    // (25:43) 
    function create_if_block_2(ctx) {
    	var input, input_updating = false, input_placeholder_value, dispose;

    	function input_input_handler_1() {
    		input_updating = true;
    		ctx.input_input_handler_1.call(input);
    	}

    	const block = {
    		c: function create() {
    			input = element("input");
    			attr_dev(input, "type", "number");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "placeholder", input_placeholder_value = ctx.param.placeholder);
    			add_location(input, file, 25, 4, 792);

    			dispose = [
    				listen_dev(input, "input", input_input_handler_1),
    				listen_dev(input, "change", ctx.edited)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, input, anchor);

    			set_input_value(input, ctx.param.model);
    		},

    		p: function update(changed, ctx) {
    			if (!input_updating && changed.param) set_input_value(input, ctx.param.model);
    			input_updating = false;

    			if ((changed.param) && input_placeholder_value !== (input_placeholder_value = ctx.param.placeholder)) {
    				attr_dev(input, "placeholder", input_placeholder_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(input);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_2.name, type: "if", source: "(25:43) ", ctx });
    	return block;
    }

    // (23:41) 
    function create_if_block_1(ctx) {
    	var input, input_placeholder_value, dispose;

    	const block = {
    		c: function create() {
    			input = element("input");
    			attr_dev(input, "type", "text");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "placeholder", input_placeholder_value = ctx.param.placeholder);
    			add_location(input, file, 23, 4, 634);

    			dispose = [
    				listen_dev(input, "input", ctx.input_input_handler),
    				listen_dev(input, "change", ctx.edited)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, input, anchor);

    			set_input_value(input, ctx.param.model);
    		},

    		p: function update(changed, ctx) {
    			if (changed.param && (input.value !== ctx.param.model)) set_input_value(input, ctx.param.model);

    			if ((changed.param) && input_placeholder_value !== (input_placeholder_value = ctx.param.placeholder)) {
    				attr_dev(input, "placeholder", input_placeholder_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(input);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1.name, type: "if", source: "(23:41) ", ctx });
    	return block;
    }

    // (14:4) {#if param.inputtype === 'select'}
    function create_if_block(ctx) {
    	var div, select, option, dispose;

    	let each_value = ctx.param.fields;

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block(get_each_context(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file, 16, 8, 393);
    			if (ctx.param.model === void 0) add_render_callback(() => ctx.select_change_handler.call(select));
    			add_location(select, file, 15, 6, 332);
    			attr_dev(div, "class", "select");
    			add_location(div, file, 14, 4, 304);

    			dispose = [
    				listen_dev(select, "change", ctx.select_change_handler),
    				listen_dev(select, "change", ctx.edited)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.param.model);
    		},

    		p: function update(changed, ctx) {
    			if (changed.param) {
    				each_value = ctx.param.fields;

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}

    			if (changed.param) select_option(select, ctx.param.model);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block.name, type: "if", source: "(14:4) {#if param.inputtype === 'select'}", ctx });
    	return block;
    }

    // (28:4) {#each param.fields as option}
    function create_each_block_1(ctx) {
    	var div, input, t0_value = ctx.option.text + "", t0, t1, dispose;

    	function input_change_handler() {
    		ctx.input_change_handler.call(input, ctx);
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			input = element("input");
    			t0 = text(t0_value);
    			t1 = space();
    			attr_dev(input, "type", "checkbox");
    			add_location(input, file, 29, 6, 1017);
    			attr_dev(div, "class", "control");
    			add_location(div, file, 28, 4, 989);

    			dispose = [
    				listen_dev(input, "change", input_change_handler),
    				listen_dev(input, "change", ctx.edited)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, input);

    			input.checked = ctx.option.checked;

    			append_dev(div, t0);
    			append_dev(div, t1);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if (changed.param) input.checked = ctx.option.checked;

    			if ((changed.param) && t0_value !== (t0_value = ctx.option.text + "")) {
    				set_data_dev(t0, t0_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1.name, type: "each", source: "(28:4) {#each param.fields as option}", ctx });
    	return block;
    }

    // (18:8) {#each param.fields as option}
    function create_each_block(ctx) {
    	var option, t_value = ctx.option.text + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.option.value;
    			option.value = option.__value;
    			add_location(option, file, 18, 8, 493);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.param) && t_value !== (t_value = ctx.option.text + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.param) && option_value_value !== (option_value_value = ctx.option.value)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block.name, type: "each", source: "(18:8) {#each param.fields as option}", ctx });
    	return block;
    }

    function create_fragment(ctx) {
    	var div1, label, t0_value = ctx.param.title + "", t0, t1, div0;

    	function select_block_type(changed, ctx) {
    		if (ctx.param.inputtype === 'select') return create_if_block;
    		if (ctx.param.inputtype === 'text') return create_if_block_1;
    		if (ctx.param.inputtype === 'number') return create_if_block_2;
    		if (ctx.param.inputtype === 'checkbox') return create_if_block_3;
    	}

    	var current_block_type = select_block_type(null, ctx);
    	var if_block = current_block_type && current_block_type(ctx);

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			label = element("label");
    			t0 = text(t0_value);
    			t1 = space();
    			div0 = element("div");
    			if (if_block) if_block.c();
    			attr_dev(label, "class", "label");
    			add_location(label, file, 11, 2, 194);
    			attr_dev(div0, "class", "control");
    			add_location(div0, file, 12, 2, 239);
    			attr_dev(div1, "class", "field");
    			add_location(div1, file, 10, 0, 172);
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, label);
    			append_dev(label, t0);
    			append_dev(div1, t1);
    			append_dev(div1, div0);
    			if (if_block) if_block.m(div0, null);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.param) && t0_value !== (t0_value = ctx.param.title + "")) {
    				set_data_dev(t0, t0_value);
    			}

    			if (current_block_type === (current_block_type = select_block_type(changed, ctx)) && if_block) {
    				if_block.p(changed, ctx);
    			} else {
    				if (if_block) if_block.d(1);
    				if_block = current_block_type && current_block_type(ctx);
    				if (if_block) {
    					if_block.c();
    					if_block.m(div0, null);
    				}
    			}
    		},

    		i: noop,
    		o: noop,

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			if (if_block) if_block.d();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment.name, type: "component", source: "", ctx });
    	return block;
    }

    function instance($$self, $$props, $$invalidate) {
    	const dispatch = createEventDispatcher();

    let { param } = $$props;

    function edited() { dispatch('edited');}

    	const writable_props = ['param'];
    	Object.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console.warn(`<Param> was created with unknown prop '${key}'`);
    	});

    	function select_change_handler() {
    		param.model = select_value(this);
    		$$invalidate('param', param);
    	}

    	function input_input_handler() {
    		param.model = this.value;
    		$$invalidate('param', param);
    	}

    	function input_input_handler_1() {
    		param.model = to_number(this.value);
    		$$invalidate('param', param);
    	}

    	function input_change_handler({ option, each_value_1, option_index_1 }) {
    		each_value_1[option_index_1].checked = this.checked;
    		$$invalidate('param', param);
    	}

    	$$self.$set = $$props => {
    		if ('param' in $$props) $$invalidate('param', param = $$props.param);
    	};

    	$$self.$capture_state = () => {
    		return { param };
    	};

    	$$self.$inject_state = $$props => {
    		if ('param' in $$props) $$invalidate('param', param = $$props.param);
    	};

    	return {
    		param,
    		edited,
    		select_change_handler,
    		input_input_handler,
    		input_input_handler_1,
    		input_change_handler
    	};
    }

    class Param extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance, create_fragment, safe_not_equal, ["param"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "Param", options, id: create_fragment.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.param === undefined && !('param' in props)) {
    			console.warn("<Param> was created without expected prop 'param'");
    		}
    	}

    	get param() {
    		throw new Error("<Param>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set param(value) {
    		throw new Error("<Param>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/ErrorNotif.svelte generated by Svelte v3.12.1 */

    const file$1 = "src/ErrorNotif.svelte";

    function get_each_context$1(ctx, list, i) {
    	const child_ctx = Object.create(ctx);
    	child_ctx.error = list[i];
    	return child_ctx;
    }

    // (16:0) {#if errors.length}
    function create_if_block$1(ctx) {
    	var div, ul, div_class_value;

    	let each_value = ctx.errors;

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$1(get_each_context$1(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			ul = element("ul");

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			add_location(ul, file$1, 17, 2, 259);
    			attr_dev(div, "class", div_class_value = "" + null_to_empty((`notification is-danger ${ctx.cssclass}`)) + " svelte-16a6jab");
    			add_location(div, file$1, 16, 0, 206);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, ul);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(ul, null);
    			}
    		},

    		p: function update(changed, ctx) {
    			if (changed.errors) {
    				each_value = ctx.errors;

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$1(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block$1(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(ul, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}

    			if ((changed.cssclass) && div_class_value !== (div_class_value = "" + null_to_empty((`notification is-danger ${ctx.cssclass}`)) + " svelte-16a6jab")) {
    				attr_dev(div, "class", div_class_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			destroy_each(each_blocks, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$1.name, type: "if", source: "(16:0) {#if errors.length}", ctx });
    	return block;
    }

    // (19:4) {#each errors as error}
    function create_each_block$1(ctx) {
    	var li, t0, t1_value = ctx.error + "", t1;

    	const block = {
    		c: function create() {
    			li = element("li");
    			t0 = text("• ");
    			t1 = text(t1_value);
    			add_location(li, file$1, 19, 4, 296);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, li, anchor);
    			append_dev(li, t0);
    			append_dev(li, t1);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.errors) && t1_value !== (t1_value = ctx.error + "")) {
    				set_data_dev(t1, t1_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(li);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$1.name, type: "each", source: "(19:4) {#each errors as error}", ctx });
    	return block;
    }

    function create_fragment$1(ctx) {
    	var if_block_anchor;

    	var if_block = (ctx.errors.length) && create_if_block$1(ctx);

    	const block = {
    		c: function create() {
    			if (if_block) if_block.c();
    			if_block_anchor = empty();
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			if (if_block) if_block.m(target, anchor);
    			insert_dev(target, if_block_anchor, anchor);
    		},

    		p: function update(changed, ctx) {
    			if (ctx.errors.length) {
    				if (if_block) {
    					if_block.p(changed, ctx);
    				} else {
    					if_block = create_if_block$1(ctx);
    					if_block.c();
    					if_block.m(if_block_anchor.parentNode, if_block_anchor);
    				}
    			} else if (if_block) {
    				if_block.d(1);
    				if_block = null;
    			}
    		},

    		i: noop,
    		o: noop,

    		d: function destroy(detaching) {
    			if (if_block) if_block.d(detaching);

    			if (detaching) {
    				detach_dev(if_block_anchor);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$1.name, type: "component", source: "", ctx });
    	return block;
    }

    function instance$1($$self, $$props, $$invalidate) {
    	let { errors, cssclass = '' } = $$props;

    	const writable_props = ['errors', 'cssclass'];
    	Object.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console.warn(`<ErrorNotif> was created with unknown prop '${key}'`);
    	});

    	$$self.$set = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    		if ('cssclass' in $$props) $$invalidate('cssclass', cssclass = $$props.cssclass);
    	};

    	$$self.$capture_state = () => {
    		return { errors, cssclass };
    	};

    	$$self.$inject_state = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    		if ('cssclass' in $$props) $$invalidate('cssclass', cssclass = $$props.cssclass);
    	};

    	return { errors, cssclass };
    }

    class ErrorNotif extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$1, create_fragment$1, safe_not_equal, ["errors", "cssclass"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "ErrorNotif", options, id: create_fragment$1.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.errors === undefined && !('errors' in props)) {
    			console.warn("<ErrorNotif> was created without expected prop 'errors'");
    		}
    	}

    	get errors() {
    		throw new Error("<ErrorNotif>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set errors(value) {
    		throw new Error("<ErrorNotif>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get cssclass() {
    		throw new Error("<ErrorNotif>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set cssclass(value) {
    		throw new Error("<ErrorNotif>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/Acquicomp.svelte generated by Svelte v3.12.1 */
    const { Object: Object_1 } = globals;

    const file$2 = "src/Acquicomp.svelte";

    function get_each_context$2(ctx, list, i) {
    	const child_ctx = Object_1.create(ctx);
    	child_ctx.param_id = list[i][0];
    	child_ctx.param = list[i][1];
    	child_ctx.each_value = list;
    	child_ctx.each_index = i;
    	return child_ctx;
    }

    function get_each_context_1$1(ctx, list, i) {
    	const child_ctx = Object_1.create(ctx);
    	child_ctx.operator = list[i];
    	return child_ctx;
    }

    // (93:19) 
    function create_if_block_2$1(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-edit");
    			add_location(i, file$2, 93, 2, 2032);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_2$1.name, type: "if", source: "(93:19) ", ctx });
    	return block;
    }

    // (91:2) {#if stored}
    function create_if_block_1$1(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-check-circle");
    			add_location(i, file$2, 91, 2, 1969);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1$1.name, type: "if", source: "(91:2) {#if stored}", ctx });
    	return block;
    }

    // (109:8) {#each acqdata.operators as operator}
    function create_each_block_1$1(ctx) {
    	var option, t_value = ctx.operator.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.operator.id;
    			option.value = option.__value;
    			add_location(option, file$2, 109, 8, 2656);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.acqdata) && t_value !== (t_value = ctx.operator.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.acqdata) && option_value_value !== (option_value_value = ctx.operator.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1$1.name, type: "each", source: "(109:8) {#each acqdata.operators as operator}", ctx });
    	return block;
    }

    // (121:4) {#if !dsinfo.dynamic_rp}
    function create_if_block$2(ctx) {
    	var input, input_updating = false, dispose;

    	function input_input_handler() {
    		input_updating = true;
    		ctx.input_input_handler.call(input);
    	}

    	const block = {
    		c: function create() {
    			input = element("input");
    			attr_dev(input, "type", "number");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "placeholder", "in minutes");
    			add_location(input, file$2, 121, 4, 2987);

    			dispose = [
    				listen_dev(input, "input", input_input_handler),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, input, anchor);

    			set_input_value(input, ctx.dsinfo.rp_length);
    		},

    		p: function update(changed, ctx) {
    			if (!input_updating && changed.dsinfo) set_input_value(input, ctx.dsinfo.rp_length);
    			input_updating = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(input);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$2.name, type: "if", source: "(121:4) {#if !dsinfo.dynamic_rp}", ctx });
    	return block;
    }

    // (127:0) {#each Object.entries(dsinfo.params) as [param_id, param]}
    function create_each_block$2(ctx) {
    	var updating_param, current;

    	function param_param_binding(value) {
    		ctx.param_param_binding.call(null, value, ctx);
    		updating_param = true;
    		add_flush_callback(() => updating_param = false);
    	}

    	let param_props = {};
    	if (ctx.param !== void 0) {
    		param_props.param = ctx.param;
    	}
    	var param = new Param({ props: param_props, $$inline: true });

    	binding_callbacks.push(() => bind(param, 'param', param_param_binding));
    	param.$on("edited", ctx.editMade);

    	const block = {
    		c: function create() {
    			param.$$.fragment.c();
    		},

    		m: function mount(target, anchor) {
    			mount_component(param, target, anchor);
    			current = true;
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			var param_changes = {};
    			if (!updating_param && changed.Object || changed.dsinfo) {
    				param_changes.param = ctx.param;
    			}
    			param.$set(param_changes);
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(param.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(param.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			destroy_component(param, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$2.name, type: "each", source: "(127:0) {#each Object.entries(dsinfo.params) as [param_id, param]}", ctx });
    	return block;
    }

    function create_fragment$2(ctx) {
    	var h5, t0, button0, t1, button0_disabled_value, t2, button1, t3, button1_disabled_value, t4, t5, div2, label0, t7, div1, div0, select, option, t9, div4, label1, t11, div3, input, t12, t13, each1_anchor, current, dispose;

    	function select_block_type(changed, ctx) {
    		if (ctx.stored) return create_if_block_1$1;
    		if (ctx.edited) return create_if_block_2$1;
    	}

    	var current_block_type = select_block_type(null, ctx);
    	var if_block0 = current_block_type && current_block_type(ctx);

    	var errornotif = new ErrorNotif({
    		props: { errors: ctx.acquierrors },
    		$$inline: true
    	});

    	let each_value_1 = ctx.acqdata.operators;

    	let each_blocks_1 = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks_1[i] = create_each_block_1$1(get_each_context_1$1(ctx, each_value_1, i));
    	}

    	var if_block1 = (!ctx.dsinfo.dynamic_rp) && create_if_block$2(ctx);

    	let each_value = ctx.Object.entries(ctx.dsinfo.params);

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$2(get_each_context$2(ctx, each_value, i));
    	}

    	const out = i => transition_out(each_blocks[i], 1, 1, () => {
    		each_blocks[i] = null;
    	});

    	const block = {
    		c: function create() {
    			h5 = element("h5");
    			if (if_block0) if_block0.c();
    			t0 = text("\n  Acquisition\n  ");
    			button0 = element("button");
    			t1 = text("Save");
    			t2 = space();
    			button1 = element("button");
    			t3 = text("Revert");
    			t4 = space();
    			errornotif.$$.fragment.c();
    			t5 = space();
    			div2 = element("div");
    			label0 = element("label");
    			label0.textContent = "Operator";
    			t7 = space();
    			div1 = element("div");
    			div0 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].c();
    			}

    			t9 = space();
    			div4 = element("div");
    			label1 = element("label");
    			label1.textContent = "Reverse phase length";
    			t11 = space();
    			div3 = element("div");
    			input = element("input");
    			t12 = text("Dynamic\n    ");
    			if (if_block1) if_block1.c();
    			t13 = space();

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			each1_anchor = empty();
    			attr_dev(button0, "class", "button is-small is-danger has-text-weight-bold");
    			button0.disabled = button0_disabled_value = !ctx.edited;
    			add_location(button0, file$2, 96, 2, 2089);
    			attr_dev(button1, "class", "button is-small is-info has-text-weight-bold");
    			button1.disabled = button1_disabled_value = !ctx.edited;
    			add_location(button1, file$2, 97, 2, 2203);
    			attr_dev(h5, "class", "has-text-primary title is-5");
    			add_location(h5, file$2, 89, 0, 1911);
    			attr_dev(label0, "class", "label");
    			add_location(label0, file$2, 103, 2, 2386);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$2, 107, 8, 2549);
    			if (ctx.dsinfo.operator_id === void 0) add_render_callback(() => ctx.select_change_handler.call(select));
    			add_location(select, file$2, 106, 6, 2479);
    			attr_dev(div0, "class", "select");
    			add_location(div0, file$2, 105, 4, 2452);
    			attr_dev(div1, "class", "control");
    			add_location(div1, file$2, 104, 2, 2426);
    			attr_dev(div2, "class", "field");
    			add_location(div2, file$2, 102, 0, 2364);
    			attr_dev(label1, "class", "label");
    			add_location(label1, file$2, 117, 2, 2791);
    			attr_dev(input, "type", "checkbox");
    			add_location(input, file$2, 119, 4, 2869);
    			attr_dev(div3, "class", "control");
    			add_location(div3, file$2, 118, 2, 2843);
    			attr_dev(div4, "class", "field");
    			add_location(div4, file$2, 116, 0, 2769);

    			dispose = [
    				listen_dev(button0, "click", ctx.save),
    				listen_dev(button1, "click", ctx.fetchData),
    				listen_dev(select, "change", ctx.select_change_handler),
    				listen_dev(select, "change", ctx.editMade),
    				listen_dev(input, "change", ctx.input_change_handler),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, h5, anchor);
    			if (if_block0) if_block0.m(h5, null);
    			append_dev(h5, t0);
    			append_dev(h5, button0);
    			append_dev(button0, t1);
    			append_dev(h5, t2);
    			append_dev(h5, button1);
    			append_dev(button1, t3);
    			insert_dev(target, t4, anchor);
    			mount_component(errornotif, target, anchor);
    			insert_dev(target, t5, anchor);
    			insert_dev(target, div2, anchor);
    			append_dev(div2, label0);
    			append_dev(div2, t7);
    			append_dev(div2, div1);
    			append_dev(div1, div0);
    			append_dev(div0, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.operator_id);

    			insert_dev(target, t9, anchor);
    			insert_dev(target, div4, anchor);
    			append_dev(div4, label1);
    			append_dev(div4, t11);
    			append_dev(div4, div3);
    			append_dev(div3, input);

    			input.checked = ctx.dsinfo.dynamic_rp;

    			append_dev(div3, t12);
    			if (if_block1) if_block1.m(div3, null);
    			insert_dev(target, t13, anchor);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(target, anchor);
    			}

    			insert_dev(target, each1_anchor, anchor);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			if (current_block_type !== (current_block_type = select_block_type(changed, ctx))) {
    				if (if_block0) if_block0.d(1);
    				if_block0 = current_block_type && current_block_type(ctx);
    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(h5, t0);
    				}
    			}

    			if ((!current || changed.edited) && button0_disabled_value !== (button0_disabled_value = !ctx.edited)) {
    				prop_dev(button0, "disabled", button0_disabled_value);
    			}

    			if ((!current || changed.edited) && button1_disabled_value !== (button1_disabled_value = !ctx.edited)) {
    				prop_dev(button1, "disabled", button1_disabled_value);
    			}

    			var errornotif_changes = {};
    			if (changed.acquierrors) errornotif_changes.errors = ctx.acquierrors;
    			errornotif.$set(errornotif_changes);

    			if (changed.acqdata) {
    				each_value_1 = ctx.acqdata.operators;

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1$1(ctx, each_value_1, i);

    					if (each_blocks_1[i]) {
    						each_blocks_1[i].p(changed, child_ctx);
    					} else {
    						each_blocks_1[i] = create_each_block_1$1(child_ctx);
    						each_blocks_1[i].c();
    						each_blocks_1[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks_1.length; i += 1) {
    					each_blocks_1[i].d(1);
    				}
    				each_blocks_1.length = each_value_1.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.operator_id);
    			if (changed.dsinfo) input.checked = ctx.dsinfo.dynamic_rp;

    			if (!ctx.dsinfo.dynamic_rp) {
    				if (if_block1) {
    					if_block1.p(changed, ctx);
    				} else {
    					if_block1 = create_if_block$2(ctx);
    					if_block1.c();
    					if_block1.m(div3, null);
    				}
    			} else if (if_block1) {
    				if_block1.d(1);
    				if_block1 = null;
    			}

    			if (changed.Object || changed.dsinfo) {
    				each_value = ctx.Object.entries(ctx.dsinfo.params);

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$2(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    						transition_in(each_blocks[i], 1);
    					} else {
    						each_blocks[i] = create_each_block$2(child_ctx);
    						each_blocks[i].c();
    						transition_in(each_blocks[i], 1);
    						each_blocks[i].m(each1_anchor.parentNode, each1_anchor);
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
    			transition_in(errornotif.$$.fragment, local);

    			for (let i = 0; i < each_value.length; i += 1) {
    				transition_in(each_blocks[i]);
    			}

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(errornotif.$$.fragment, local);

    			each_blocks = each_blocks.filter(Boolean);
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				transition_out(each_blocks[i]);
    			}

    			current = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(h5);
    			}

    			if (if_block0) if_block0.d();

    			if (detaching) {
    				detach_dev(t4);
    			}

    			destroy_component(errornotif, detaching);

    			if (detaching) {
    				detach_dev(t5);
    				detach_dev(div2);
    			}

    			destroy_each(each_blocks_1, detaching);

    			if (detaching) {
    				detach_dev(t9);
    				detach_dev(div4);
    			}

    			if (if_block1) if_block1.d();

    			if (detaching) {
    				detach_dev(t13);
    			}

    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(each1_anchor);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$2.name, type: "component", source: "", ctx });
    	return block;
    }

    function instance$2($$self, $$props, $$invalidate) {
    	let $dataset_id;

    	validate_store(dataset_id, 'dataset_id');
    	component_subscribe($$self, dataset_id, $$value => { $dataset_id = $$value; $$invalidate('$dataset_id', $dataset_id); });

    	

    let { errors } = $$props;

    let acquierrors = [];


    let dsinfo = {
      operator_id: '',
      dynamic_rp: false,
      rp_length: '',
      params: [],
    };

    let acqdata = {
      operators: [],
    };

    let edited = false;

    function editMade() { 
      $$invalidate('errors', errors = errors.length ? validate() : []);
      $$invalidate('edited', edited = true);
    }

    function validate() {
      let comperrors = [];
    	if (!dsinfo.operator_id) {
    		comperrors.push('Operator is required');
    	}
    	if (!dsinfo.dynamic_rp && !dsinfo.rp_length) {
    		comperrors.push('Reverse phase is required');
    	}
    	for (let key in dsinfo.params) {
        if (!dsinfo.params[key].model) {
    			comperrors.push(dsinfo.params[key].title + ' is required');
    		}
    	}
      return comperrors;
    }

    async function save() {
      $$invalidate('acquierrors', acquierrors = []);
      $$invalidate('errors', errors = validate());
      if (errors.length === 0) { 
        let postdata = {
          dataset_id: $dataset_id,
          operator_id: dsinfo.operator_id,
          params: dsinfo.params,
          rp_length: dsinfo.dynamic_rp ? '' : dsinfo.rp_length,
        };
        let url = '/datasets/save/acquisition/';
        try {
          const resp = await postJSON(url, postdata);
          fetchData();
        } catch(error) {
          if (error.message === '404') { 
            $$invalidate('acquierrors', acquierrors = [...acquierrors, 'Save dataset before saving acquisition']);
          }
        }
      }
    }


    async function fetchData() {
      let url = '/datasets/show/acquisition/';
      url = $dataset_id ? url + $dataset_id : url;
    	const response = await getJSON(url);
      for (let [key, val] of Object.entries(response.acqdata)) { $$invalidate('acqdata', acqdata[key] = val, acqdata); }
      for (let [key, val] of Object.entries(response.dsinfo)) { $$invalidate('dsinfo', dsinfo[key] = val, dsinfo); }
      $$invalidate('edited', edited = false);
    }

    onMount(async() => {
      fetchData();
    });

    	const writable_props = ['errors'];
    	Object_1.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console.warn(`<Acquicomp> was created with unknown prop '${key}'`);
    	});

    	function select_change_handler() {
    		dsinfo.operator_id = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('acqdata', acqdata);
    	}

    	function input_change_handler() {
    		dsinfo.dynamic_rp = this.checked;
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('acqdata', acqdata);
    	}

    	function input_input_handler() {
    		dsinfo.rp_length = to_number(this.value);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('acqdata', acqdata);
    	}

    	function param_param_binding(value, { param, each_value, each_index }) {
    		each_value[each_index][1] = value;
    		$$invalidate('Object', Object);
    	}

    	$$self.$set = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    	};

    	$$self.$capture_state = () => {
    		return { errors, acquierrors, dsinfo, acqdata, edited, stored, $dataset_id };
    	};

    	$$self.$inject_state = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    		if ('acquierrors' in $$props) $$invalidate('acquierrors', acquierrors = $$props.acquierrors);
    		if ('dsinfo' in $$props) $$invalidate('dsinfo', dsinfo = $$props.dsinfo);
    		if ('acqdata' in $$props) $$invalidate('acqdata', acqdata = $$props.acqdata);
    		if ('edited' in $$props) $$invalidate('edited', edited = $$props.edited);
    		if ('stored' in $$props) $$invalidate('stored', stored = $$props.stored);
    		if ('$dataset_id' in $$props) dataset_id.set($dataset_id);
    	};

    	let stored;

    	$$self.$$.update = ($$dirty = { $dataset_id: 1, edited: 1 }) => {
    		if ($$dirty.$dataset_id || $$dirty.edited) { $$invalidate('stored', stored = $dataset_id && !edited); }
    	};

    	return {
    		errors,
    		acquierrors,
    		dsinfo,
    		acqdata,
    		edited,
    		editMade,
    		validate,
    		save,
    		fetchData,
    		stored,
    		Object,
    		select_change_handler,
    		input_change_handler,
    		input_input_handler,
    		param_param_binding
    	};
    }

    class Acquicomp extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$2, create_fragment$2, safe_not_equal, ["errors", "validate", "save"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "Acquicomp", options, id: create_fragment$2.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.errors === undefined && !('errors' in props)) {
    			console.warn("<Acquicomp> was created without expected prop 'errors'");
    		}
    		if (ctx.validate === undefined && !('validate' in props)) {
    			console.warn("<Acquicomp> was created without expected prop 'validate'");
    		}
    		if (ctx.save === undefined && !('save' in props)) {
    			console.warn("<Acquicomp> was created without expected prop 'save'");
    		}
    	}

    	get errors() {
    		throw new Error("<Acquicomp>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set errors(value) {
    		throw new Error("<Acquicomp>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get validate() {
    		return this.$$.ctx.validate;
    	}

    	set validate(value) {
    		throw new Error("<Acquicomp>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get save() {
    		return this.$$.ctx.save;
    	}

    	set save(value) {
    		throw new Error("<Acquicomp>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/DynamicSelect.svelte generated by Svelte v3.12.1 */
    const { Object: Object_1$1, console: console_1 } = globals;

    const file$3 = "src/DynamicSelect.svelte";

    function get_each_context$3(ctx, list, i) {
    	const child_ctx = Object_1$1.create(ctx);
    	child_ctx.optid = list[i];
    	return child_ctx;
    }

    // (82:2) {#if typing}
    function create_if_block$3(ctx) {
    	var div, select, show_if = !ctx.Object.keys(ctx.options).length, if_block_anchor;

    	var if_block = (show_if) && create_if_block_1$2(ctx);

    	let each_value = ctx.optorder;

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$3(get_each_context$3(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			select = element("select");
    			if (if_block) if_block.c();
    			if_block_anchor = empty();

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			select.multiple = true;
    			add_location(select, file$3, 83, 4, 2453);
    			attr_dev(div, "class", "select is-multiple");
    			add_location(div, file$3, 82, 2, 2416);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, select);
    			if (if_block) if_block.m(select, null);
    			append_dev(select, if_block_anchor);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}
    		},

    		p: function update(changed, ctx) {
    			if (changed.options) show_if = !ctx.Object.keys(ctx.options).length;

    			if (show_if) {
    				if (!if_block) {
    					if_block = create_if_block_1$2(ctx);
    					if_block.c();
    					if_block.m(select, if_block_anchor);
    				}
    			} else if (if_block) {
    				if_block.d(1);
    				if_block = null;
    			}

    			if (changed.optorder || changed.niceName || changed.options) {
    				each_value = ctx.optorder;

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$3(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block$3(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			if (if_block) if_block.d();

    			destroy_each(each_blocks, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$3.name, type: "if", source: "(82:2) {#if typing}", ctx });
    	return block;
    }

    // (85:6) {#if !Object.keys(options).length}
    function create_if_block_1$2(ctx) {
    	var option;

    	const block = {
    		c: function create() {
    			option = element("option");
    			option.textContent = "Type more or type less...";
    			option.disabled = true;
    			option.__value = "Type more or type less...";
    			option.value = option.__value;
    			add_location(option, file$3, 85, 6, 2518);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1$2.name, type: "if", source: "(85:6) {#if !Object.keys(options).length}", ctx });
    	return block;
    }

    // (88:6) {#each optorder as optid}
    function create_each_block$3(ctx) {
    	var option, t_value = ctx.niceName(ctx.options[ctx.optid]) + "", t, option_value_value, dispose;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.optid;
    			option.value = option.__value;
    			add_location(option, file$3, 88, 6, 2621);

    			dispose = [
    				listen_dev(option, "mousedown", ctx.mousedown_handler),
    				listen_dev(option, "mouseout", ctx.mouseout_handler),
    				listen_dev(option, "mouseover", ctx.mouseover_handler)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.niceName || changed.options || changed.optorder) && t_value !== (t_value = ctx.niceName(ctx.options[ctx.optid]) + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.optorder) && option_value_value !== (option_value_value = ctx.optid)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$3.name, type: "each", source: "(88:6) {#each optorder as optid}", ctx });
    	return block;
    }

    function create_fragment$3(ctx) {
    	var div, input, t0, span, i, t1, dispose;

    	var if_block = (ctx.typing) && create_if_block$3(ctx);

    	const block = {
    		c: function create() {
    			div = element("div");
    			input = element("input");
    			t0 = space();
    			span = element("span");
    			i = element("i");
    			t1 = space();
    			if (if_block) if_block.c();
    			attr_dev(input, "type", "text");
    			attr_dev(input, "class", "input is-narrow");
    			attr_dev(input, "placeholder", ctx.placeholder);
    			add_location(input, file$3, 78, 2, 2168);
    			attr_dev(i, "class", "fas fa-chevron-down");
    			add_location(i, file$3, 79, 30, 2355);
    			attr_dev(span, "class", "icon is-right");
    			add_location(span, file$3, 79, 2, 2327);
    			attr_dev(div, "class", "control has-icons-right");
    			add_location(div, file$3, 77, 0, 2128);

    			dispose = [
    				listen_dev(input, "input", ctx.input_input_handler),
    				listen_dev(input, "keyup", ctx.fetchOptions),
    				listen_dev(input, "focus", ctx.starttyping),
    				listen_dev(input, "blur", ctx.inputdone)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, input);

    			set_input_value(input, ctx.intext);

    			append_dev(div, t0);
    			append_dev(div, span);
    			append_dev(span, i);
    			append_dev(div, t1);
    			if (if_block) if_block.m(div, null);
    		},

    		p: function update(changed, ctx) {
    			if (changed.intext && (input.value !== ctx.intext)) set_input_value(input, ctx.intext);

    			if (changed.placeholder) {
    				attr_dev(input, "placeholder", ctx.placeholder);
    			}

    			if (ctx.typing) {
    				if (if_block) {
    					if_block.p(changed, ctx);
    				} else {
    					if_block = create_if_block$3(ctx);
    					if_block.c();
    					if_block.m(div, null);
    				}
    			} else if (if_block) {
    				if_block.d(1);
    				if_block = null;
    			}
    		},

    		i: noop,
    		o: noop,

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			if (if_block) if_block.d();
    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$3.name, type: "component", source: "", ctx });
    	return block;
    }

    function instance$3($$self, $$props, $$invalidate) {
    	

    const dispatch = createEventDispatcher();

    let { selectval = '', fixedoptions = {}, fixedorder = [], options = Object.fromEntries(Object.entries(fixedoptions)), intext, fetchUrl = false, niceName = function(text) { return text; } } = $$props;
    let { unknowninput = '__PLACEHOLDER__', optorder = fixedorder.length ? fixedorder : Object.keys(options) } = $$props;

    let selectedtext;
    let placeholder = 'Filter by typing';
    let typing = false;


    function inputdone() {
      $$invalidate('typing', typing = false);
      if (selectval && selectval in options) {
        $$invalidate('intext', intext = niceName(options[selectval]));
      } else if (unknowninput === '__PLACEHOLDER__') {
        console.log('illegal value');
        dispatch('illegalvalue');
      } else {
        console.log('new value');
        $$invalidate('unknowninput', unknowninput = intext);
        dispatch('newvalue');
      }
    }

    function deselect(ev) {
      ev.target.selected = false;
      $$invalidate('intext', intext = '');
      $$invalidate('placeholder', placeholder = selectval ? niceName(selectval) : '');
    }

    function selectvalue(ev) {
      $$invalidate('selectval', selectval = options[ev.target.value].id);
      $$invalidate('unknowninput', unknowninput = '');
      dispatch('selectedvalue'); 
    }

    function hovervalue(ev) {
      ev.target.selected = true;
      const val = options[ev.target.value];
      $$invalidate('intext', intext = niceName(val));
    }

    async function fetchOptions() {
      if (intext.length > 2 && fetchUrl) {
        $$invalidate('options', options = await getJSON(`${fetchUrl}?q=${intext}`));
        $$invalidate('optorder', optorder = Object.keys(options));
      } else if (!fetchUrl && fixedoptions) {
        $$invalidate('options', options = Object.fromEntries(Object.entries(fixedoptions).filter(x => x[1].name.toLowerCase().indexOf(intext.toLowerCase()) > -1)));
        const keys = Object.keys(options);
        $$invalidate('optorder', optorder = fixedorder.length ? fixedorder.filter(x => keys.indexOf(x.toString()) > -1) : keys);
      }
    }

    function starttyping() {
      const keys = Object.keys(options);
      $$invalidate('optorder', optorder = fixedorder.length ? fixedorder : keys);
      $$invalidate('options', options = fixedorder.length ? fixedoptions : options);
      $$invalidate('typing', typing = true);
      $$invalidate('placeholder', placeholder = selectval ? niceName(selectval) : '');
      $$invalidate('selectval', selectval = '');
      $$invalidate('intext', intext = '');
    }

    	const writable_props = ['selectval', 'fixedoptions', 'fixedorder', 'options', 'intext', 'fetchUrl', 'niceName', 'unknowninput', 'optorder'];
    	Object_1$1.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console_1.warn(`<DynamicSelect> was created with unknown prop '${key}'`);
    	});

    	function input_input_handler() {
    		intext = this.value;
    		$$invalidate('intext', intext);
    	}

    	const mousedown_handler = (e) => selectvalue(e);

    	const mouseout_handler = (e) => deselect(e);

    	const mouseover_handler = (e) => hovervalue(e);

    	$$self.$set = $$props => {
    		if ('selectval' in $$props) $$invalidate('selectval', selectval = $$props.selectval);
    		if ('fixedoptions' in $$props) $$invalidate('fixedoptions', fixedoptions = $$props.fixedoptions);
    		if ('fixedorder' in $$props) $$invalidate('fixedorder', fixedorder = $$props.fixedorder);
    		if ('options' in $$props) $$invalidate('options', options = $$props.options);
    		if ('intext' in $$props) $$invalidate('intext', intext = $$props.intext);
    		if ('fetchUrl' in $$props) $$invalidate('fetchUrl', fetchUrl = $$props.fetchUrl);
    		if ('niceName' in $$props) $$invalidate('niceName', niceName = $$props.niceName);
    		if ('unknowninput' in $$props) $$invalidate('unknowninput', unknowninput = $$props.unknowninput);
    		if ('optorder' in $$props) $$invalidate('optorder', optorder = $$props.optorder);
    	};

    	$$self.$capture_state = () => {
    		return { selectval, fixedoptions, fixedorder, options, intext, fetchUrl, niceName, unknowninput, optorder, selectedtext, placeholder, typing };
    	};

    	$$self.$inject_state = $$props => {
    		if ('selectval' in $$props) $$invalidate('selectval', selectval = $$props.selectval);
    		if ('fixedoptions' in $$props) $$invalidate('fixedoptions', fixedoptions = $$props.fixedoptions);
    		if ('fixedorder' in $$props) $$invalidate('fixedorder', fixedorder = $$props.fixedorder);
    		if ('options' in $$props) $$invalidate('options', options = $$props.options);
    		if ('intext' in $$props) $$invalidate('intext', intext = $$props.intext);
    		if ('fetchUrl' in $$props) $$invalidate('fetchUrl', fetchUrl = $$props.fetchUrl);
    		if ('niceName' in $$props) $$invalidate('niceName', niceName = $$props.niceName);
    		if ('unknowninput' in $$props) $$invalidate('unknowninput', unknowninput = $$props.unknowninput);
    		if ('optorder' in $$props) $$invalidate('optorder', optorder = $$props.optorder);
    		if ('selectedtext' in $$props) selectedtext = $$props.selectedtext;
    		if ('placeholder' in $$props) $$invalidate('placeholder', placeholder = $$props.placeholder);
    		if ('typing' in $$props) $$invalidate('typing', typing = $$props.typing);
    	};

    	return {
    		selectval,
    		fixedoptions,
    		fixedorder,
    		options,
    		intext,
    		fetchUrl,
    		niceName,
    		unknowninput,
    		optorder,
    		placeholder,
    		typing,
    		inputdone,
    		deselect,
    		selectvalue,
    		hovervalue,
    		fetchOptions,
    		starttyping,
    		Object,
    		input_input_handler,
    		mousedown_handler,
    		mouseout_handler,
    		mouseover_handler
    	};
    }

    class DynamicSelect extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$3, create_fragment$3, safe_not_equal, ["selectval", "fixedoptions", "fixedorder", "options", "intext", "fetchUrl", "niceName", "unknowninput", "optorder"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "DynamicSelect", options, id: create_fragment$3.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.intext === undefined && !('intext' in props)) {
    			console_1.warn("<DynamicSelect> was created without expected prop 'intext'");
    		}
    	}

    	get selectval() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set selectval(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get fixedoptions() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set fixedoptions(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get fixedorder() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set fixedorder(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get options() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set options(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get intext() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set intext(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get fetchUrl() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set fetchUrl(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get niceName() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set niceName(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get unknowninput() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set unknowninput(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get optorder() {
    		throw new Error("<DynamicSelect>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set optorder(value) {
    		throw new Error("<DynamicSelect>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/Prepcomp.svelte generated by Svelte v3.12.1 */
    const { Object: Object_1$2, console: console_1$1 } = globals;

    const file$4 = "src/Prepcomp.svelte";

    function get_each_context_4(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.s_id = list[i][0];
    	child_ctx.sample = list[i][1];
    	return child_ctx;
    }

    function get_each_context_3(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.s_id = list[i][0];
    	child_ctx.sample = list[i][1];
    	return child_ctx;
    }

    function get_each_context_2(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.file = list[i];
    	return child_ctx;
    }

    function get_each_context_1$2(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.s_id = list[i][0];
    	child_ctx.sample = list[i][1];
    	return child_ctx;
    }

    function get_each_context$4(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.channel = list[i];
    	child_ctx.each_value = list;
    	child_ctx.chix = i;
    	return child_ctx;
    }

    function get_each_context_5(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.quant = list[i];
    	return child_ctx;
    }

    function get_each_context_6(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.param_id = list[i][0];
    	child_ctx.param = list[i][1];
    	child_ctx.each_value_6 = list;
    	child_ctx.each_index_3 = i;
    	return child_ctx;
    }

    function get_each_context_7(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.enzyme = list[i];
    	child_ctx.each_value_7 = list;
    	child_ctx.enzyme_index = i;
    	return child_ctx;
    }

    function get_each_context_8(ctx, list, i) {
    	const child_ctx = Object_1$2.create(ctx);
    	child_ctx.spec = list[i];
    	return child_ctx;
    }

    // (311:19) 
    function create_if_block_11(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-edit");
    			add_location(i, file$4, 311, 2, 10120);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_11.name, type: "if", source: "(311:19) ", ctx });
    	return block;
    }

    // (309:2) {#if stored}
    function create_if_block_10(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-check-circle");
    			add_location(i, file$4, 309, 2, 10057);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_10.name, type: "if", source: "(309:2) {#if stored}", ctx });
    	return block;
    }

    // (326:2) {#each prepdata.species as spec}
    function create_each_block_8(ctx) {
    	var span, t0_value = niceSpecies(ctx.spec) + "", t0, t1, button, t2, dispose;

    	function click_handler(...args) {
    		return ctx.click_handler(ctx, ...args);
    	}

    	const block = {
    		c: function create() {
    			span = element("span");
    			t0 = text(t0_value);
    			t1 = space();
    			button = element("button");
    			t2 = space();
    			attr_dev(button, "class", "delete is-small");
    			add_location(button, file$4, 328, 4, 10896);
    			attr_dev(span, "class", "tag is-medium is-info");
    			add_location(span, file$4, 326, 2, 10831);
    			dispose = listen_dev(button, "click", click_handler);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, t0);
    			append_dev(span, t1);
    			append_dev(span, button);
    			append_dev(span, t2);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if ((changed.prepdata) && t0_value !== (t0_value = niceSpecies(ctx.spec) + "")) {
    				set_data_dev(t0, t0_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(span);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_8.name, type: "each", source: "(326:2) {#each prepdata.species as spec}", ctx });
    	return block;
    }

    // (337:2) {#if !prepdata.no_enzyme}
    function create_if_block_9(ctx) {
    	var each_1_anchor;

    	let each_value_7 = ctx.prepdata.enzymes;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_7.length; i += 1) {
    		each_blocks[i] = create_each_block_7(get_each_context_7(ctx, each_value_7, i));
    	}

    	const block = {
    		c: function create() {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			each_1_anchor = empty();
    		},

    		m: function mount(target, anchor) {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(target, anchor);
    			}

    			insert_dev(target, each_1_anchor, anchor);
    		},

    		p: function update(changed, ctx) {
    			if (changed.prepdata) {
    				each_value_7 = ctx.prepdata.enzymes;

    				let i;
    				for (i = 0; i < each_value_7.length; i += 1) {
    					const child_ctx = get_each_context_7(ctx, each_value_7, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_7(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(each_1_anchor.parentNode, each_1_anchor);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_7.length;
    			}
    		},

    		d: function destroy(detaching) {
    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(each_1_anchor);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_9.name, type: "if", source: "(337:2) {#if !prepdata.no_enzyme}", ctx });
    	return block;
    }

    // (338:2) {#each prepdata.enzymes as enzyme}
    function create_each_block_7(ctx) {
    	var div, input, t0_value = ctx.enzyme.name + "", t0, t1, dispose;

    	function input_change_handler_1() {
    		ctx.input_change_handler_1.call(input, ctx);
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			input = element("input");
    			t0 = text(t0_value);
    			t1 = space();
    			attr_dev(input, "type", "checkbox");
    			add_location(input, file$4, 339, 4, 11246);
    			attr_dev(div, "class", "control");
    			add_location(div, file$4, 338, 2, 11220);

    			dispose = [
    				listen_dev(input, "change", input_change_handler_1),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, input);

    			input.checked = ctx.enzyme.checked;

    			append_dev(div, t0);
    			append_dev(div, t1);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if (changed.prepdata) input.checked = ctx.enzyme.checked;

    			if ((changed.prepdata) && t0_value !== (t0_value = ctx.enzyme.name + "")) {
    				set_data_dev(t0, t0_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_7.name, type: "each", source: "(338:2) {#each prepdata.enzymes as enzyme}", ctx });
    	return block;
    }

    // (346:0) {#each Object.entries(prepdata.params) as [param_id, param]}
    function create_each_block_6(ctx) {
    	var updating_param, current;

    	function param_param_binding(value) {
    		ctx.param_param_binding.call(null, value, ctx);
    		updating_param = true;
    		add_flush_callback(() => updating_param = false);
    	}

    	let param_props = {};
    	if (ctx.param !== void 0) {
    		param_props.param = ctx.param;
    	}
    	var param = new Param({ props: param_props, $$inline: true });

    	binding_callbacks.push(() => bind(param, 'param', param_param_binding));
    	param.$on("edited", ctx.editMade);

    	const block = {
    		c: function create() {
    			param.$$.fragment.c();
    		},

    		m: function mount(target, anchor) {
    			mount_component(param, target, anchor);
    			current = true;
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			var param_changes = {};
    			if (!updating_param && changed.Object || changed.prepdata) {
    				param_changes.param = ctx.param;
    			}
    			param.$set(param_changes);
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(param.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(param.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			destroy_component(param, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_6.name, type: "each", source: "(346:0) {#each Object.entries(prepdata.params) as [param_id, param]}", ctx });
    	return block;
    }

    // (357:8) {#each Object.values(prepdata.quants) as quant}
    function create_each_block_5(ctx) {
    	var option, t_value = ctx.quant.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.quant.id;
    			option.value = option.__value;
    			add_location(option, file$4, 357, 8, 11803);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.Object || changed.prepdata) && t_value !== (t_value = ctx.quant.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.Object || changed.prepdata) && option_value_value !== (option_value_value = ctx.quant.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_5.name, type: "each", source: "(357:8) {#each Object.values(prepdata.quants) as quant}", ctx });
    	return block;
    }

    // (365:0) {#if prepdata.quanttype}
    function create_if_block$4(ctx) {
    	var div1, label, t1, textarea, t2, a, t4, div0, t5, table, thead, tr, t6, th, t7, t8, tbody, show_if, dispose;

    	var if_block0 = (ctx.isLabelfree) && create_if_block_8(ctx);

    	function select_block_type_1(changed, ctx) {
    		if (ctx.isLabelfree && ctx.prepdata.labelfree_multisample) return create_if_block_6;
    		if (!ctx.isLabelfree) return create_if_block_7;
    	}

    	var current_block_type = select_block_type_1(null, ctx);
    	var if_block1 = current_block_type && current_block_type(ctx);

    	function select_block_type_2(changed, ctx) {
    		if (ctx.foundNewSamples) return create_if_block_5;
    		return create_else_block;
    	}

    	var current_block_type_1 = select_block_type_2(null, ctx);
    	var if_block2 = current_block_type_1(ctx);

    	function select_block_type_3(changed, ctx) {
    		if (!ctx.isLabelfree) return create_if_block_1$3;
    		if (ctx.isLabelfree && ctx.prepdata.labelfree_multisample) return create_if_block_3$1;
    		if ((show_if == null) || changed.isLabelfree || changed.Object || changed.$datasetFiles) show_if = !!(ctx.isLabelfree && ctx.Object.keys(ctx.$datasetFiles).length);
    		if (show_if) return create_if_block_4;
    	}

    	var current_block_type_2 = select_block_type_3(null, ctx);
    	var if_block3 = current_block_type_2 && current_block_type_2(ctx);

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			label = element("label");
    			label.textContent = "Samples";
    			t1 = space();
    			textarea = element("textarea");
    			t2 = space();
    			a = element("a");
    			a.textContent = "Parse sample names";
    			t4 = space();
    			div0 = element("div");
    			if (if_block0) if_block0.c();
    			t5 = space();
    			table = element("table");
    			thead = element("thead");
    			tr = element("tr");
    			if (if_block1) if_block1.c();
    			t6 = space();
    			th = element("th");
    			t7 = text("Sample name \n        ");
    			if_block2.c();
    			t8 = space();
    			tbody = element("tbody");
    			if (if_block3) if_block3.c();
    			attr_dev(label, "class", "label");
    			add_location(label, file$4, 366, 2, 11957);
    			attr_dev(textarea, "class", "textarea");
    			attr_dev(textarea, "placeholder", "Try this: paste your sample names here (one line per sample, tab separated sample/file or channel)");
    			add_location(textarea, file$4, 367, 2, 11996);
    			attr_dev(a, "class", "button is-primary");
    			add_location(a, file$4, 368, 2, 12178);
    			attr_dev(div0, "class", "control");
    			add_location(div0, file$4, 369, 2, 12260);
    			attr_dev(div1, "class", "field");
    			add_location(div1, file$4, 365, 0, 11935);
    			attr_dev(th, "colspan", "2");
    			add_location(th, file$4, 385, 6, 12709);
    			add_location(tr, file$4, 379, 4, 12550);
    			add_location(thead, file$4, 378, 2, 12538);
    			add_location(tbody, file$4, 394, 2, 13032);
    			attr_dev(table, "class", "table is-fullwidth");
    			add_location(table, file$4, 377, 0, 12500);

    			dispose = [
    				listen_dev(textarea, "input", ctx.textarea_input_handler),
    				listen_dev(a, "click", ctx.parseSampleNames)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, label);
    			append_dev(div1, t1);
    			append_dev(div1, textarea);

    			set_input_value(textarea, ctx.trysamplenames);

    			append_dev(div1, t2);
    			append_dev(div1, a);
    			append_dev(div1, t4);
    			append_dev(div1, div0);
    			if (if_block0) if_block0.m(div0, null);
    			insert_dev(target, t5, anchor);
    			insert_dev(target, table, anchor);
    			append_dev(table, thead);
    			append_dev(thead, tr);
    			if (if_block1) if_block1.m(tr, null);
    			append_dev(tr, t6);
    			append_dev(tr, th);
    			append_dev(th, t7);
    			if_block2.m(th, null);
    			append_dev(table, t8);
    			append_dev(table, tbody);
    			if (if_block3) if_block3.m(tbody, null);
    		},

    		p: function update(changed, ctx) {
    			if (changed.trysamplenames) set_input_value(textarea, ctx.trysamplenames);

    			if (ctx.isLabelfree) {
    				if (if_block0) {
    					if_block0.p(changed, ctx);
    				} else {
    					if_block0 = create_if_block_8(ctx);
    					if_block0.c();
    					if_block0.m(div0, null);
    				}
    			} else if (if_block0) {
    				if_block0.d(1);
    				if_block0 = null;
    			}

    			if (current_block_type !== (current_block_type = select_block_type_1(changed, ctx))) {
    				if (if_block1) if_block1.d(1);
    				if_block1 = current_block_type && current_block_type(ctx);
    				if (if_block1) {
    					if_block1.c();
    					if_block1.m(tr, t6);
    				}
    			}

    			if (current_block_type_1 !== (current_block_type_1 = select_block_type_2(changed, ctx))) {
    				if_block2.d(1);
    				if_block2 = current_block_type_1(ctx);
    				if (if_block2) {
    					if_block2.c();
    					if_block2.m(th, null);
    				}
    			}

    			if (current_block_type_2 === (current_block_type_2 = select_block_type_3(changed, ctx)) && if_block3) {
    				if_block3.p(changed, ctx);
    			} else {
    				if (if_block3) if_block3.d(1);
    				if_block3 = current_block_type_2 && current_block_type_2(ctx);
    				if (if_block3) {
    					if_block3.c();
    					if_block3.m(tbody, null);
    				}
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			if (if_block0) if_block0.d();

    			if (detaching) {
    				detach_dev(t5);
    				detach_dev(table);
    			}

    			if (if_block1) if_block1.d();
    			if_block2.d();
    			if (if_block3) if_block3.d();
    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$4.name, type: "if", source: "(365:0) {#if prepdata.quanttype}", ctx });
    	return block;
    }

    // (371:4) {#if isLabelfree}
    function create_if_block_8(ctx) {
    	var div, input, t, dispose;

    	const block = {
    		c: function create() {
    			div = element("div");
    			input = element("input");
    			t = text("One sample per file?");
    			attr_dev(input, "type", "checkbox");
    			add_location(input, file$4, 372, 6, 12343);
    			attr_dev(div, "id", "labelfree_samples");
    			add_location(div, file$4, 371, 4, 12308);

    			dispose = [
    				listen_dev(input, "change", ctx.input_change_handler_2),
    				listen_dev(input, "change", ctx.checkIfNewSamples)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, input);

    			input.checked = ctx.prepdata.labelfree_multisample;

    			append_dev(div, t);
    		},

    		p: function update(changed, ctx) {
    			if (changed.prepdata) input.checked = ctx.prepdata.labelfree_multisample;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_8.name, type: "if", source: "(371:4) {#if isLabelfree}", ctx });
    	return block;
    }

    // (383:29) 
    function create_if_block_7(ctx) {
    	var th;

    	const block = {
    		c: function create() {
    			th = element("th");
    			th.textContent = "Channel";
    			add_location(th, file$4, 383, 6, 12673);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, th, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(th);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_7.name, type: "if", source: "(383:29) ", ctx });
    	return block;
    }

    // (381:6) {#if isLabelfree && prepdata.labelfree_multisample}
    function create_if_block_6(ctx) {
    	var th;

    	const block = {
    		c: function create() {
    			th = element("th");
    			th.textContent = "Filename";
    			add_location(th, file$4, 381, 6, 12619);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, th, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(th);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_6.name, type: "if", source: "(381:6) {#if isLabelfree && prepdata.labelfree_multisample}", ctx });
    	return block;
    }

    // (389:8) {:else}
    function create_else_block(ctx) {
    	var a;

    	const block = {
    		c: function create() {
    			a = element("a");
    			a.textContent = "Save new samples";
    			attr_dev(a, "class", "button is-danger is-small is-pulled-right");
    			attr_dev(a, "disabled", "");
    			add_location(a, file$4, 389, 8, 12900);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, a, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(a);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_else_block.name, type: "else", source: "(389:8) {:else}", ctx });
    	return block;
    }

    // (387:8) {#if foundNewSamples}
    function create_if_block_5(ctx) {
    	var a, dispose;

    	const block = {
    		c: function create() {
    			a = element("a");
    			a.textContent = "Save new samples";
    			attr_dev(a, "class", "button is-danger is-small is-pulled-right");
    			add_location(a, file$4, 387, 8, 12776);
    			dispose = listen_dev(a, "click", ctx.saveNewSamples);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, a, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(a);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_5.name, type: "if", source: "(387:8) {#if foundNewSamples}", ctx });
    	return block;
    }

    // (439:63) 
    function create_if_block_4(ctx) {
    	var tr, td0, div, select, option, t_1, td1, input, dispose;

    	let each_value_4 = ctx.Object.entries(projsamples);

    	let each_blocks = [];

    	for (let i = 0; i < each_value_4.length; i += 1) {
    		each_blocks[i] = create_each_block_4(get_each_context_4(ctx, each_value_4, i));
    	}

    	const block = {
    		c: function create() {
    			tr = element("tr");
    			td0 = element("td");
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Pick a project-sample";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t_1 = space();
    			td1 = element("td");
    			input = element("input");
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$4, 442, 12, 15108);
    			if (ctx.prepdata.labelfree_singlesample.model === void 0) add_render_callback(() => ctx.select_change_handler_3.call(select));
    			add_location(select, file$4, 441, 10, 14967);
    			attr_dev(div, "class", "select");
    			add_location(div, file$4, 440, 8, 14936);
    			add_location(td0, file$4, 439, 8, 14923);
    			attr_dev(input, "placeholder", "or define a new sample");
    			attr_dev(input, "class", "input is-normal");
    			add_location(input, file$4, 449, 10, 15364);
    			add_location(td1, file$4, 449, 6, 15360);
    			add_location(tr, file$4, 439, 4, 14919);

    			dispose = [
    				listen_dev(select, "change", ctx.select_change_handler_3),
    				listen_dev(select, "change", ctx.change_handler_4),
    				listen_dev(input, "input", ctx.input_input_handler_2),
    				listen_dev(input, "change", ctx.change_handler_5)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tr, anchor);
    			append_dev(tr, td0);
    			append_dev(td0, div);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.prepdata.labelfree_singlesample.model);

    			append_dev(tr, t_1);
    			append_dev(tr, td1);
    			append_dev(td1, input);

    			set_input_value(input, ctx.prepdata.labelfree_singlesample.newprojsample);
    		},

    		p: function update(changed, ctx) {
    			if (changed.Object || changed.projsamples) {
    				each_value_4 = ctx.Object.entries(projsamples);

    				let i;
    				for (i = 0; i < each_value_4.length; i += 1) {
    					const child_ctx = get_each_context_4(ctx, each_value_4, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_4(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_4.length;
    			}

    			if (changed.prepdata) select_option(select, ctx.prepdata.labelfree_singlesample.model);
    			if (changed.prepdata && (input.value !== ctx.prepdata.labelfree_singlesample.newprojsample)) set_input_value(input, ctx.prepdata.labelfree_singlesample.newprojsample);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(tr);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_4.name, type: "if", source: "(439:63) ", ctx });
    	return block;
    }

    // (422:60) 
    function create_if_block_3$1(ctx) {
    	var each_1_anchor;

    	let each_value_2 = ctx.Object.values(ctx.$datasetFiles);

    	let each_blocks = [];

    	for (let i = 0; i < each_value_2.length; i += 1) {
    		each_blocks[i] = create_each_block_2(get_each_context_2(ctx, each_value_2, i));
    	}

    	const block = {
    		c: function create() {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			each_1_anchor = empty();
    		},

    		m: function mount(target, anchor) {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(target, anchor);
    			}

    			insert_dev(target, each_1_anchor, anchor);
    		},

    		p: function update(changed, ctx) {
    			if (changed.prepdata || changed.Object || changed.$datasetFiles || changed.projsamples) {
    				each_value_2 = ctx.Object.values(ctx.$datasetFiles);

    				let i;
    				for (i = 0; i < each_value_2.length; i += 1) {
    					const child_ctx = get_each_context_2(ctx, each_value_2, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_2(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(each_1_anchor.parentNode, each_1_anchor);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_2.length;
    			}
    		},

    		d: function destroy(detaching) {
    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(each_1_anchor);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_3$1.name, type: "if", source: "(422:60) ", ctx });
    	return block;
    }

    // (396:4) {#if !isLabelfree}
    function create_if_block_1$3(ctx) {
    	var each_1_anchor;

    	let each_value = ctx.prepdata.quants[ctx.prepdata.quanttype].chans;

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$4(get_each_context$4(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			each_1_anchor = empty();
    		},

    		m: function mount(target, anchor) {
    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(target, anchor);
    			}

    			insert_dev(target, each_1_anchor, anchor);
    		},

    		p: function update(changed, ctx) {
    			if (changed.prepdata || changed.foundNewSamples || changed.Object || changed.projsamples) {
    				each_value = ctx.prepdata.quants[ctx.prepdata.quanttype].chans;

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$4(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block$4(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(each_1_anchor.parentNode, each_1_anchor);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}
    		},

    		d: function destroy(detaching) {
    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(each_1_anchor);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1$3.name, type: "if", source: "(396:4) {#if !isLabelfree}", ctx });
    	return block;
    }

    // (444:12) {#each Object.entries(projsamples) as [s_id, sample]}
    function create_each_block_4(ctx) {
    	var option, t_value = ctx.sample.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.s_id;
    			option.value = option.__value;
    			add_location(option, file$4, 444, 12, 15243);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.Object || changed.projsamples) && t_value !== (t_value = ctx.sample.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.Object || changed.projsamples) && option_value_value !== (option_value_value = ctx.s_id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_4.name, type: "each", source: "(444:12) {#each Object.entries(projsamples) as [s_id, sample]}", ctx });
    	return block;
    }

    // (430:12) {#each Object.entries(projsamples) as [s_id, sample]}
    function create_each_block_3(ctx) {
    	var option, t_value = ctx.sample.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.s_id;
    			option.value = option.__value;
    			add_location(option, file$4, 430, 12, 14520);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.Object || changed.projsamples) && t_value !== (t_value = ctx.sample.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.Object || changed.projsamples) && option_value_value !== (option_value_value = ctx.s_id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_3.name, type: "each", source: "(430:12) {#each Object.entries(projsamples) as [s_id, sample]}", ctx });
    	return block;
    }

    // (423:4) {#each Object.values($datasetFiles) as file}
    function create_each_block_2(ctx) {
    	var tr, td0, t0_value = ctx.file.name + "", t0, t1, td1, div, select, option, t3, td2, input, t4, dispose;

    	let each_value_3 = ctx.Object.entries(projsamples);

    	let each_blocks = [];

    	for (let i = 0; i < each_value_3.length; i += 1) {
    		each_blocks[i] = create_each_block_3(get_each_context_3(ctx, each_value_3, i));
    	}

    	function select_change_handler_2() {
    		ctx.select_change_handler_2.call(select, ctx);
    	}

    	function change_handler_2(...args) {
    		return ctx.change_handler_2(ctx, ...args);
    	}

    	function input_input_handler_1() {
    		ctx.input_input_handler_1.call(input, ctx);
    	}

    	function change_handler_3(...args) {
    		return ctx.change_handler_3(ctx, ...args);
    	}

    	const block = {
    		c: function create() {
    			tr = element("tr");
    			td0 = element("td");
    			t0 = text(t0_value);
    			t1 = space();
    			td1 = element("td");
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Pick a project-sample";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t3 = space();
    			td2 = element("td");
    			input = element("input");
    			t4 = space();
    			add_location(td0, file$4, 424, 6, 14174);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$4, 428, 12, 14385);
    			if (ctx.prepdata.samples[ctx.file.associd].model === void 0) add_render_callback(select_change_handler_2);
    			add_location(select, file$4, 427, 10, 14245);
    			attr_dev(div, "class", "select");
    			add_location(div, file$4, 426, 8, 14214);
    			add_location(td1, file$4, 425, 6, 14201);
    			attr_dev(input, "placeholder", "or define a new sample");
    			attr_dev(input, "class", "input is-normal");
    			add_location(input, file$4, 435, 10, 14641);
    			add_location(td2, file$4, 435, 6, 14637);
    			add_location(tr, file$4, 423, 4, 14163);

    			dispose = [
    				listen_dev(select, "change", select_change_handler_2),
    				listen_dev(select, "change", change_handler_2),
    				listen_dev(input, "input", input_input_handler_1),
    				listen_dev(input, "change", change_handler_3)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tr, anchor);
    			append_dev(tr, td0);
    			append_dev(td0, t0);
    			append_dev(tr, t1);
    			append_dev(tr, td1);
    			append_dev(td1, div);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.prepdata.samples[ctx.file.associd].model);

    			append_dev(tr, t3);
    			append_dev(tr, td2);
    			append_dev(td2, input);

    			set_input_value(input, ctx.prepdata.samples[ctx.file.associd].newprojsample);

    			append_dev(tr, t4);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if ((changed.Object || changed.$datasetFiles) && t0_value !== (t0_value = ctx.file.name + "")) {
    				set_data_dev(t0, t0_value);
    			}

    			if (changed.Object || changed.projsamples) {
    				each_value_3 = ctx.Object.entries(projsamples);

    				let i;
    				for (i = 0; i < each_value_3.length; i += 1) {
    					const child_ctx = get_each_context_3(ctx, each_value_3, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_3(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_3.length;
    			}

    			if ((changed.prepdata || changed.Object || changed.$datasetFiles)) select_option(select, ctx.prepdata.samples[ctx.file.associd].model);
    			if ((changed.prepdata || changed.Object || changed.$datasetFiles) && (input.value !== ctx.prepdata.samples[ctx.file.associd].newprojsample)) set_input_value(input, ctx.prepdata.samples[ctx.file.associd].newprojsample);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(tr);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_2.name, type: "each", source: "(423:4) {#each Object.values($datasetFiles) as file}", ctx });
    	return block;
    }

    // (404:12) {#each Object.entries(projsamples) as [s_id, sample]}
    function create_each_block_1$2(ctx) {
    	var option, t_value = ctx.sample.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.s_id;
    			option.value = option.__value;
    			add_location(option, file$4, 404, 12, 13451);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.Object || changed.projsamples) && t_value !== (t_value = ctx.sample.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.Object || changed.projsamples) && option_value_value !== (option_value_value = ctx.s_id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1$2.name, type: "each", source: "(404:12) {#each Object.entries(projsamples) as [s_id, sample]}", ctx });
    	return block;
    }

    // (413:8) {#if foundNewSamples && channel.newprojsample}
    function create_if_block_2$2(ctx) {
    	var span, i;

    	const block = {
    		c: function create() {
    			span = element("span");
    			i = element("i");
    			attr_dev(i, "class", "fas fa-asterisk");
    			add_location(i, file$4, 414, 10, 13940);
    			attr_dev(span, "class", "icon is-left has-text-danger");
    			add_location(span, file$4, 413, 8, 13886);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, i);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(span);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_2$2.name, type: "if", source: "(413:8) {#if foundNewSamples && channel.newprojsample}", ctx });
    	return block;
    }

    // (397:4) {#each prepdata.quants[prepdata.quanttype].chans as channel, chix}
    function create_each_block$4(ctx) {
    	var tr, td0, t0_value = ctx.channel.name + "", t0, t1, td1, div, select, option, t3, td2, p, input, t4, p_class_value, t5, dispose;

    	let each_value_1 = ctx.Object.entries(projsamples);

    	let each_blocks = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks[i] = create_each_block_1$2(get_each_context_1$2(ctx, each_value_1, i));
    	}

    	function select_change_handler_1() {
    		ctx.select_change_handler_1.call(select, ctx);
    	}

    	function change_handler(...args) {
    		return ctx.change_handler(ctx, ...args);
    	}

    	function input_input_handler() {
    		ctx.input_input_handler.call(input, ctx);
    	}

    	function change_handler_1(...args) {
    		return ctx.change_handler_1(ctx, ...args);
    	}

    	var if_block = (ctx.foundNewSamples && ctx.channel.newprojsample) && create_if_block_2$2(ctx);

    	const block = {
    		c: function create() {
    			tr = element("tr");
    			td0 = element("td");
    			t0 = text(t0_value);
    			t1 = space();
    			td1 = element("td");
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Pick a project-sample";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t3 = space();
    			td2 = element("td");
    			p = element("p");
    			input = element("input");
    			t4 = space();
    			if (if_block) if_block.c();
    			t5 = space();
    			add_location(td0, file$4, 398, 6, 13149);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$4, 402, 12, 13316);
    			if (ctx.channel.model === void 0) add_render_callback(select_change_handler_1);
    			add_location(select, file$4, 401, 10, 13223);
    			attr_dev(div, "class", "select");
    			add_location(div, file$4, 400, 8, 13192);
    			add_location(td1, file$4, 399, 6, 13179);
    			attr_dev(input, "class", "input is-normal");
    			attr_dev(input, "placeholder", "or define a new sample");
    			add_location(input, file$4, 411, 8, 13681);
    			attr_dev(p, "class", p_class_value = ctx.channel.newprojsample && ctx.foundNewSamples ? 'control has-icons-left' : 'control');
    			add_location(p, file$4, 410, 8, 13581);
    			add_location(td2, file$4, 409, 6, 13568);
    			add_location(tr, file$4, 397, 4, 13138);

    			dispose = [
    				listen_dev(select, "change", select_change_handler_1),
    				listen_dev(select, "change", change_handler),
    				listen_dev(input, "input", input_input_handler),
    				listen_dev(input, "change", change_handler_1)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tr, anchor);
    			append_dev(tr, td0);
    			append_dev(td0, t0);
    			append_dev(tr, t1);
    			append_dev(tr, td1);
    			append_dev(td1, div);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.channel.model);

    			append_dev(tr, t3);
    			append_dev(tr, td2);
    			append_dev(td2, p);
    			append_dev(p, input);

    			set_input_value(input, ctx.channel.newprojsample);

    			append_dev(p, t4);
    			if (if_block) if_block.m(p, null);
    			append_dev(tr, t5);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if ((changed.prepdata) && t0_value !== (t0_value = ctx.channel.name + "")) {
    				set_data_dev(t0, t0_value);
    			}

    			if (changed.Object || changed.projsamples) {
    				each_value_1 = ctx.Object.entries(projsamples);

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1$2(ctx, each_value_1, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_1$2(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_1.length;
    			}

    			if (changed.prepdata) select_option(select, ctx.channel.model);
    			if (changed.prepdata && (input.value !== ctx.channel.newprojsample)) set_input_value(input, ctx.channel.newprojsample);

    			if (ctx.foundNewSamples && ctx.channel.newprojsample) {
    				if (!if_block) {
    					if_block = create_if_block_2$2(ctx);
    					if_block.c();
    					if_block.m(p, null);
    				}
    			} else if (if_block) {
    				if_block.d(1);
    				if_block = null;
    			}

    			if ((changed.prepdata || changed.foundNewSamples) && p_class_value !== (p_class_value = ctx.channel.newprojsample && ctx.foundNewSamples ? 'control has-icons-left' : 'control')) {
    				attr_dev(p, "class", p_class_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(tr);
    			}

    			destroy_each(each_blocks, detaching);

    			if (if_block) if_block.d();
    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$4.name, type: "each", source: "(397:4) {#each prepdata.quants[prepdata.quanttype].chans as channel, chix}", ctx });
    	return block;
    }

    function create_fragment$4(ctx) {
    	var h5, t0, button0, t1, button0_disabled_value, t2, button1, t3, button1_disabled_value, t4, t5, div0, label0, t7, updating_options, updating_selectval, t8, div1, t9, div2, label1, t11, input, t12, t13, t14, div5, label2, t16, div4, div3, select, option, t18, if_block2_anchor, current, dispose;

    	function select_block_type(changed, ctx) {
    		if (ctx.stored) return create_if_block_10;
    		if (ctx.edited) return create_if_block_11;
    	}

    	var current_block_type = select_block_type(null, ctx);
    	var if_block0 = current_block_type && current_block_type(ctx);

    	var errornotif = new ErrorNotif({
    		props: { errors: ctx.preperrors },
    		$$inline: true
    	});

    	function dynamicselect_options_binding(value) {
    		ctx.dynamicselect_options_binding.call(null, value);
    		updating_options = true;
    		add_flush_callback(() => updating_options = false);
    	}

    	function dynamicselect_selectval_binding(value_1) {
    		ctx.dynamicselect_selectval_binding.call(null, value_1);
    		updating_selectval = true;
    		add_flush_callback(() => updating_selectval = false);
    	}

    	let dynamicselect_props = {
    		intext: "Type to get more organisms",
    		optorder: ctx.Object.keys(ctx.prepdata.allspecies),
    		fetchUrl: "/datasets/show/species/",
    		niceName: niceSpecies
    	};
    	if (ctx.prepdata.allspecies !== void 0) {
    		dynamicselect_props.options = ctx.prepdata.allspecies;
    	}
    	if (ctx.selectedspecies !== void 0) {
    		dynamicselect_props.selectval = ctx.selectedspecies;
    	}
    	var dynamicselect = new DynamicSelect({
    		props: dynamicselect_props,
    		$$inline: true
    	});

    	binding_callbacks.push(() => bind(dynamicselect, 'options', dynamicselect_options_binding));
    	binding_callbacks.push(() => bind(dynamicselect, 'selectval', dynamicselect_selectval_binding));
    	dynamicselect.$on("selectedvalue", ctx.addOrganism);

    	let each_value_8 = ctx.prepdata.species;

    	let each_blocks_2 = [];

    	for (let i = 0; i < each_value_8.length; i += 1) {
    		each_blocks_2[i] = create_each_block_8(get_each_context_8(ctx, each_value_8, i));
    	}

    	var if_block1 = (!ctx.prepdata.no_enzyme) && create_if_block_9(ctx);

    	let each_value_6 = ctx.Object.entries(ctx.prepdata.params);

    	let each_blocks_1 = [];

    	for (let i = 0; i < each_value_6.length; i += 1) {
    		each_blocks_1[i] = create_each_block_6(get_each_context_6(ctx, each_value_6, i));
    	}

    	const out = i => transition_out(each_blocks_1[i], 1, 1, () => {
    		each_blocks_1[i] = null;
    	});

    	let each_value_5 = ctx.Object.values(ctx.prepdata.quants);

    	let each_blocks = [];

    	for (let i = 0; i < each_value_5.length; i += 1) {
    		each_blocks[i] = create_each_block_5(get_each_context_5(ctx, each_value_5, i));
    	}

    	var if_block2 = (ctx.prepdata.quanttype) && create_if_block$4(ctx);

    	const block = {
    		c: function create() {
    			h5 = element("h5");
    			if (if_block0) if_block0.c();
    			t0 = text("\n  Sample prep\n  ");
    			button0 = element("button");
    			t1 = text("Save");
    			t2 = space();
    			button1 = element("button");
    			t3 = text("Revert");
    			t4 = space();
    			errornotif.$$.fragment.c();
    			t5 = space();
    			div0 = element("div");
    			label0 = element("label");
    			label0.textContent = "Organism";
    			t7 = space();
    			dynamicselect.$$.fragment.c();
    			t8 = space();
    			div1 = element("div");

    			for (let i = 0; i < each_blocks_2.length; i += 1) {
    				each_blocks_2[i].c();
    			}

    			t9 = space();
    			div2 = element("div");
    			label1 = element("label");
    			label1.textContent = "Enzymes";
    			t11 = space();
    			input = element("input");
    			t12 = text("No enzyme\n  ");
    			if (if_block1) if_block1.c();
    			t13 = space();

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].c();
    			}

    			t14 = space();
    			div5 = element("div");
    			label2 = element("label");
    			label2.textContent = "Quant type";
    			t16 = space();
    			div4 = element("div");
    			div3 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t18 = space();
    			if (if_block2) if_block2.c();
    			if_block2_anchor = empty();
    			attr_dev(button0, "class", "button is-small is-danger has-text-weight-bold");
    			button0.disabled = button0_disabled_value = !ctx.edited;
    			add_location(button0, file$4, 314, 2, 10177);
    			attr_dev(button1, "class", "button is-small is-info has-text-weight-bold");
    			button1.disabled = button1_disabled_value = !ctx.edited;
    			add_location(button1, file$4, 315, 2, 10291);
    			attr_dev(h5, "id", "sampleprep");
    			attr_dev(h5, "class", "has-text-primary title is-5");
    			add_location(h5, file$4, 307, 0, 9983);
    			attr_dev(label0, "class", "label");
    			add_location(label0, file$4, 321, 2, 10473);
    			attr_dev(div0, "class", "field");
    			add_location(div0, file$4, 320, 0, 10451);
    			attr_dev(div1, "class", "tags");
    			add_location(div1, file$4, 324, 0, 10775);
    			attr_dev(label1, "class", "label");
    			add_location(label1, file$4, 334, 2, 11026);
    			attr_dev(input, "type", "checkbox");
    			add_location(input, file$4, 335, 2, 11065);
    			attr_dev(div2, "class", "field");
    			add_location(div2, file$4, 333, 0, 11004);
    			attr_dev(label2, "class", "label");
    			add_location(label2, file$4, 351, 2, 11512);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$4, 355, 8, 11686);
    			if (ctx.prepdata.quanttype === void 0) add_render_callback(() => ctx.select_change_handler.call(select));
    			add_location(select, file$4, 354, 6, 11607);
    			attr_dev(div3, "class", "select");
    			add_location(div3, file$4, 353, 4, 11580);
    			attr_dev(div4, "class", "control");
    			add_location(div4, file$4, 352, 2, 11554);
    			attr_dev(div5, "class", "field");
    			add_location(div5, file$4, 350, 0, 11490);

    			dispose = [
    				listen_dev(button0, "click", ctx.save),
    				listen_dev(button1, "click", ctx.fetchData),
    				listen_dev(input, "change", ctx.input_change_handler),
    				listen_dev(input, "change", ctx.editMade),
    				listen_dev(select, "change", ctx.select_change_handler),
    				listen_dev(select, "change", ctx.checkIfNewSamples)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, h5, anchor);
    			if (if_block0) if_block0.m(h5, null);
    			append_dev(h5, t0);
    			append_dev(h5, button0);
    			append_dev(button0, t1);
    			append_dev(h5, t2);
    			append_dev(h5, button1);
    			append_dev(button1, t3);
    			insert_dev(target, t4, anchor);
    			mount_component(errornotif, target, anchor);
    			insert_dev(target, t5, anchor);
    			insert_dev(target, div0, anchor);
    			append_dev(div0, label0);
    			append_dev(div0, t7);
    			mount_component(dynamicselect, div0, null);
    			insert_dev(target, t8, anchor);
    			insert_dev(target, div1, anchor);

    			for (let i = 0; i < each_blocks_2.length; i += 1) {
    				each_blocks_2[i].m(div1, null);
    			}

    			insert_dev(target, t9, anchor);
    			insert_dev(target, div2, anchor);
    			append_dev(div2, label1);
    			append_dev(div2, t11);
    			append_dev(div2, input);

    			input.checked = ctx.prepdata.no_enzyme;

    			append_dev(div2, t12);
    			if (if_block1) if_block1.m(div2, null);
    			insert_dev(target, t13, anchor);

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].m(target, anchor);
    			}

    			insert_dev(target, t14, anchor);
    			insert_dev(target, div5, anchor);
    			append_dev(div5, label2);
    			append_dev(div5, t16);
    			append_dev(div5, div4);
    			append_dev(div4, div3);
    			append_dev(div3, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.prepdata.quanttype);

    			insert_dev(target, t18, anchor);
    			if (if_block2) if_block2.m(target, anchor);
    			insert_dev(target, if_block2_anchor, anchor);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			if (current_block_type !== (current_block_type = select_block_type(changed, ctx))) {
    				if (if_block0) if_block0.d(1);
    				if_block0 = current_block_type && current_block_type(ctx);
    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(h5, t0);
    				}
    			}

    			if ((!current || changed.edited) && button0_disabled_value !== (button0_disabled_value = !ctx.edited)) {
    				prop_dev(button0, "disabled", button0_disabled_value);
    			}

    			if ((!current || changed.edited) && button1_disabled_value !== (button1_disabled_value = !ctx.edited)) {
    				prop_dev(button1, "disabled", button1_disabled_value);
    			}

    			var errornotif_changes = {};
    			if (changed.preperrors) errornotif_changes.errors = ctx.preperrors;
    			errornotif.$set(errornotif_changes);

    			var dynamicselect_changes = {};
    			if (changed.Object || changed.prepdata) dynamicselect_changes.optorder = ctx.Object.keys(ctx.prepdata.allspecies);
    			if (!updating_options && changed.prepdata) {
    				dynamicselect_changes.options = ctx.prepdata.allspecies;
    			}
    			if (!updating_selectval && changed.selectedspecies) {
    				dynamicselect_changes.selectval = ctx.selectedspecies;
    			}
    			dynamicselect.$set(dynamicselect_changes);

    			if (changed.niceSpecies || changed.prepdata) {
    				each_value_8 = ctx.prepdata.species;

    				let i;
    				for (i = 0; i < each_value_8.length; i += 1) {
    					const child_ctx = get_each_context_8(ctx, each_value_8, i);

    					if (each_blocks_2[i]) {
    						each_blocks_2[i].p(changed, child_ctx);
    					} else {
    						each_blocks_2[i] = create_each_block_8(child_ctx);
    						each_blocks_2[i].c();
    						each_blocks_2[i].m(div1, null);
    					}
    				}

    				for (; i < each_blocks_2.length; i += 1) {
    					each_blocks_2[i].d(1);
    				}
    				each_blocks_2.length = each_value_8.length;
    			}

    			if (changed.prepdata) input.checked = ctx.prepdata.no_enzyme;

    			if (!ctx.prepdata.no_enzyme) {
    				if (if_block1) {
    					if_block1.p(changed, ctx);
    				} else {
    					if_block1 = create_if_block_9(ctx);
    					if_block1.c();
    					if_block1.m(div2, null);
    				}
    			} else if (if_block1) {
    				if_block1.d(1);
    				if_block1 = null;
    			}

    			if (changed.Object || changed.prepdata) {
    				each_value_6 = ctx.Object.entries(ctx.prepdata.params);

    				let i;
    				for (i = 0; i < each_value_6.length; i += 1) {
    					const child_ctx = get_each_context_6(ctx, each_value_6, i);

    					if (each_blocks_1[i]) {
    						each_blocks_1[i].p(changed, child_ctx);
    						transition_in(each_blocks_1[i], 1);
    					} else {
    						each_blocks_1[i] = create_each_block_6(child_ctx);
    						each_blocks_1[i].c();
    						transition_in(each_blocks_1[i], 1);
    						each_blocks_1[i].m(t14.parentNode, t14);
    					}
    				}

    				group_outros();
    				for (i = each_value_6.length; i < each_blocks_1.length; i += 1) {
    					out(i);
    				}
    				check_outros();
    			}

    			if (changed.Object || changed.prepdata) {
    				each_value_5 = ctx.Object.values(ctx.prepdata.quants);

    				let i;
    				for (i = 0; i < each_value_5.length; i += 1) {
    					const child_ctx = get_each_context_5(ctx, each_value_5, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_5(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_5.length;
    			}

    			if (changed.prepdata) select_option(select, ctx.prepdata.quanttype);

    			if (ctx.prepdata.quanttype) {
    				if (if_block2) {
    					if_block2.p(changed, ctx);
    				} else {
    					if_block2 = create_if_block$4(ctx);
    					if_block2.c();
    					if_block2.m(if_block2_anchor.parentNode, if_block2_anchor);
    				}
    			} else if (if_block2) {
    				if_block2.d(1);
    				if_block2 = null;
    			}
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(errornotif.$$.fragment, local);

    			transition_in(dynamicselect.$$.fragment, local);

    			for (let i = 0; i < each_value_6.length; i += 1) {
    				transition_in(each_blocks_1[i]);
    			}

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(errornotif.$$.fragment, local);
    			transition_out(dynamicselect.$$.fragment, local);

    			each_blocks_1 = each_blocks_1.filter(Boolean);
    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				transition_out(each_blocks_1[i]);
    			}

    			current = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(h5);
    			}

    			if (if_block0) if_block0.d();

    			if (detaching) {
    				detach_dev(t4);
    			}

    			destroy_component(errornotif, detaching);

    			if (detaching) {
    				detach_dev(t5);
    				detach_dev(div0);
    			}

    			destroy_component(dynamicselect);

    			if (detaching) {
    				detach_dev(t8);
    				detach_dev(div1);
    			}

    			destroy_each(each_blocks_2, detaching);

    			if (detaching) {
    				detach_dev(t9);
    				detach_dev(div2);
    			}

    			if (if_block1) if_block1.d();

    			if (detaching) {
    				detach_dev(t13);
    			}

    			destroy_each(each_blocks_1, detaching);

    			if (detaching) {
    				detach_dev(t14);
    				detach_dev(div5);
    			}

    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(t18);
    			}

    			if (if_block2) if_block2.d(detaching);

    			if (detaching) {
    				detach_dev(if_block2_anchor);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$4.name, type: "component", source: "", ctx });
    	return block;
    }

    function niceSpecies(species) { 
    let nice;
    if (species.name) {
      nice = `${species.name}, ${species.linnean}`;
    } else {
      nice = `${species.linnean}`;
    }
    return nice;
    }

    function instance$4($$self, $$props, $$invalidate) {
    	let $dataset_id, $datasetFiles;

    	validate_store(dataset_id, 'dataset_id');
    	component_subscribe($$self, dataset_id, $$value => { $dataset_id = $$value; $$invalidate('$dataset_id', $dataset_id); });
    	validate_store(datasetFiles, 'datasetFiles');
    	component_subscribe($$self, datasetFiles, $$value => { $datasetFiles = $$value; $$invalidate('$datasetFiles', $datasetFiles); });

    	

    let { errors } = $$props;

    let preperrors = [];
    let edited = false;

    function editMade() { 
      $$invalidate('errors', errors = errors.length ? validate() : []);
      $$invalidate('edited', edited = true); 
    }

    let prepdata = {
      params: [],
      enzymes: [],
      no_enzyme: false,
      quanttype: '',
      quants: {},
      labelfree_multisample: true,
      labelfree_singlesample: {},
      allspecies: [],
      species: [],
      samples: {},
    };

    let selectedspecies;
    let trysamplenames = '';
    let labelfree_quant_id;
    let foundNewSamples = false;

    function removeOrganism(org_id) {
      $$invalidate('prepdata', prepdata.species = prepdata.species.filter(x => x.id !== org_id), prepdata);
      editMade();
    }

    function addOrganism() {
      $$invalidate('prepdata', prepdata.species = [...prepdata.species, prepdata.allspecies[selectedspecies]], prepdata);
      editMade();
    }


    function checkIfNewSamples() {
      /* checks if ANY sample in current quanttype is a newprojectsample, enabling save button */
      if (prepdata.quanttype !== labelfree_quant_id) { // Cannot check isLabelfree here, that is slower to update than the call to this func
        $$invalidate('foundNewSamples', foundNewSamples = prepdata.quants[prepdata.quanttype].chans.some(ch => ch.newprojsample !== ''));
      } else if (!prepdata.labelfree_multisample) {
        $$invalidate('foundNewSamples', foundNewSamples = prepdata.labelfree_singlesample.newprojsample !== '');
      } else {
        $$invalidate('foundNewSamples', foundNewSamples = Object.values(prepdata.samples).some(x => x.newprojsample !== ''));
      }
    }

    function checkNewSampleLabelfree(associd=false) {
      /* Checks if entered sample is found in project or if it is a new sample */
      let sample;
      if (!prepdata.labelfree_multisample) {
        sample = prepdata.labelfree_singlesample.newprojsample;
      } else {
        sample = prepdata.samples[associd].newprojsample;
      }
      if (sample == '') { 
        return 
      } else {
        let uppername = sample.trim().toUpperCase();
        let found = Object.entries(projsamples).filter(x=>x[1].toUpperCase() == uppername).map(x=>x[0])[0];
        if (found && !prepdata.labelfree_multisample) {
          $$invalidate('prepdata', prepdata.labelfree_singlesample.model = found, prepdata);
          $$invalidate('prepdata', prepdata.labelfree_singlesample.newprojsample = '', prepdata);
        } else if (found) {
          $$invalidate('prepdata', prepdata.samples[associd].model = found, prepdata);
          $$invalidate('prepdata', prepdata.samples[associd].newprojsample = '', prepdata);
          /* new samples filled in will reset the dropdown ones, do not do this, only on save */
    //    }  else if (prepdata.labelfree_multisample) {
    //      prepdata.samples[associd].model = '';
    //    } else {
    //      prepdata.labelfree_singlesample.model = '';
        }
        checkIfNewSamples();
      }
    }

    function checkNewSample(chanix) {
      /* Checks if entered sample is found in project or if it is a new sample */
      
      if (prepdata.quants[prepdata.quanttype].chans[chanix].newprojsample == '') { 
        /* at fetchdata, samples are assigned, on:change fires and this is called */
        return 
      } else {
        let uppername = prepdata.quants[prepdata.quanttype].chans[chanix].newprojsample.trim().toUpperCase();
        let found = Object.entries(projsamples).filter(x=>x[1].toUpperCase() == uppername).map(x=>x[0])[0];
        if (found) {
          $$invalidate('prepdata', prepdata.quants[prepdata.quanttype].chans[chanix].model = found, prepdata);
          $$invalidate('prepdata', prepdata.quants[prepdata.quanttype].chans[chanix].newprojsample = '', prepdata);
        }
        checkIfNewSamples();
      }
    }

    function parseSampleNames() {
      /* Parses samples/files/channel combinations pasted in textbox */
      let ixmap = {};
      let fnmap = {};
      if (isLabelfree && !prepdata.labelfree_multisample) {
        return 0;
      } else if (isLabelfree) {
        for (let fn of Object.values($datasetFiles)) {
          fnmap[fn.name] = fn;
        }
      } else {
        prepdata.quants[prepdata.quanttype].chans.forEach(function(ch, ix) {
          ixmap[ch.name] = ix;
        });
        }
      for (let line of trysamplenames.trim().split('\n')) {
        if (line.indexOf('\t') > -1) {
          line = line.trim().split('\t').map(x => x.trim());
        } else if (line.indexOf('    ') > -1) {
          line = line.trim().split('    ').map(x => x.trim());
        }
        let nps, ix, aid;
        if (isLabelfree) {
          line[0] in fnmap ? (aid = fnmap[line[0]], nps = line[1]) : false;
          line[1] in fnmap ? (aid = fnmap[line[1]], nps = line[0]) : false;
          aid ? $$invalidate('prepdata', prepdata.samples[aid.associd].newprojsample = nps, prepdata) : false;
        } else {
          line[0] in ixmap ? (ix = ixmap[line[0]], nps = line[1]) : false;
          line[1] in ixmap ? (ix = ixmap[line[1]], nps = line[0]) : false;
          ix ? $$invalidate('prepdata', prepdata.quants[prepdata.quanttype].chans[ix].newprojsample = nps, prepdata) : false;
        }
      }
      editMade();
    }

    function resetNewSampleName(chan_or_sample) {
      chan_or_sample.newprojsample = '';
      checkIfNewSamples();
      editMade();
    }

    async function doSampleSave(ch_or_samfn, ix) { 
      /* Saves a new sample name to the project on backend */
      let postdata = {
        dataset_id: $dataset_id, 
        samplename: ch_or_samfn.newprojsample
      };
      let url = '/datasets/save/projsample/';
      try {
        const response = await postJSON(url, postdata);
      } catch(error) {
        if (error.message === '404') {
          $$invalidate('preperrors', preperrors = [preperrors, 'Save dataset before saving new samples']);
        }
        return;
      }
      // just add the latest projsample, do not just assign the whole projsamples dict, async problems!
      projsamples[response.psid] = response.psname;
      return [response.psid, ix];
    }

    async function saveNewSamples() {
      /* Goes through each of the new sample names and */
      let saves = [];
      if (!isLabelfree) {
        prepdata.quants[prepdata.quanttype].chans.map(function(ch, ix) { return [ix, ch]}).filter(ch => ch[1].newprojsample).forEach(function(ch) {
          saves.push(doSampleSave(ch[1], ch[0]));
        }); 
        console.log(saves);
        for (let item of saves) {
          let [psid, ix] = await item;
          $$invalidate('prepdata', prepdata.quants[prepdata.quanttype].chans[ix].newprojsample = '', prepdata);
          $$invalidate('prepdata', prepdata.quants[prepdata.quanttype].chans[ix].model = psid, prepdata);
        }
      } else if (!prepdata.labelfree_multisample && foundNewSamples) {
        const savedsample = await doSampleSave(prepdata.labelfree_singlesample);
        $$invalidate('prepdata', prepdata.labelfree_singlesample.model = savedsample[0], prepdata);
        $$invalidate('prepdata', prepdata.labelfree_singlesample.newprojsample = '', prepdata);
      } else {
        Object.entries(prepdata.samples).filter(x => x[1].newprojsample).forEach(function(samfn) {
          saves.push(doSampleSave(samfn[1], samfn[0]));
        });
        for (let item of saves) {
          let [psid, associd] = await item;
          $$invalidate('prepdata', prepdata.samples[associd].newprojsample = '', prepdata);
          $$invalidate('prepdata', prepdata.samples[associd].model = psid, prepdata);
        }
      }
      checkIfNewSamples();
    }

    function validate() {
      let comperrors = [];
    	if (!prepdata.no_enzyme && !prepdata.enzymes.filter.length) {
    		comperrors.push('Enzyme selection is required');
    	}
    	if (!prepdata.quanttype) {
    		comperrors.push('Quant type selection is required');
    	}
      if (isLabelfree && prepdata.labelfree_multisample) {
    		for (let fn of Object.values($datasetFiles)) {
    			if (!prepdata.samples[fn.associd].model && !prepdata.samples[fn.associd].newprojsample) {
    				comperrors.push('Labelfree requires sample name for each file');
    				break;
    			}
    		}	
      } else if (isLabelfree) {
        if (prepdata.labelfree_singlesample.model === '') {
          comperrors.push('Labelfree singlesample requires a sample name');
        }
    	} else if (prepdata.quanttype in prepdata.quants) {
    		for (let ch of prepdata.quants[prepdata.quanttype].chans) {
    			if (ch.model === '') { 
    				comperrors.push('Sample name for each channel is required');
    				break;
    			}
    		}
    	}
      for (let param of Object.values(prepdata.params).filter(p => p.inputtype !== 'checkbox')) {
        if (!param.model) {
    			comperrors.push(param.title + ' is required');
    		}
    	}
      for (let param of Object.values(prepdata.params).filter(p => p.inputtype === 'checkbox')) {
        if (!param.fields.some(f => f.checked)) {
    			comperrors.push(param.title + ' is required');
    		}
    	}
    	if (!Object.keys(prepdata.species).length) {
    		comperrors.push('Organism(s) is/are required');
    	}
      return comperrors;
    }

    async function save() {
      $$invalidate('errors', errors = validate());
      if (!Object.keys($datasetFiles).length && isLabelfree) {
        $$invalidate('preperrors', preperrors = [...preperrors, 'Add files before saving data']);
      }
      if (!$dataset_id) {
        $$invalidate('preperrors', preperrors = [...preperrors, 'Save dataset before saving sample prep']);
      }
      if (errors.length === 0 && preperrors.length === 0) { 
        let postdata = {
          dataset_id: $dataset_id,
          enzymes: prepdata.no_enzyme ? [] : prepdata.enzymes,
          params: prepdata.params,
          quanttype: prepdata.quanttype,
          labelfree: isLabelfree,
          species: prepdata.species,
        };
        if (!isLabelfree) {
          postdata.samples = prepdata.quants[prepdata.quanttype].chans;
        } else if (prepdata.labelfree_multisample) {
          postdata.filenames = Object.values($datasetFiles);
          postdata.samples = prepdata.samples;
        } else {
          postdata.filenames = Object.values($datasetFiles);
          postdata.samples = Object.fromEntries(postdata.filenames.map(fn => [fn.associd, prepdata.labelfree_singlesample]));
        }
        let url = '/datasets/save/sampleprep/';
        await postJSON(url, postdata);
        fetchData();
      }
    }

    async function fetchData() {
      let url = '/datasets/show/sampleprep/';
      url = $dataset_id ? url + $dataset_id : url;
    	const response = await getJSON(url);
      for (let [key, val] of Object.entries(response)) { $$invalidate('prepdata', prepdata[key] = val, prepdata); }
      $$invalidate('labelfree_quant_id', labelfree_quant_id = Object.entries(prepdata.quants).filter(x => x[1].name === 'labelfree').map(x=>Number(x[0])).pop());
      $$invalidate('edited', edited = false);
    }

    onMount(async() => {
      await fetchData();
    });

    	const writable_props = ['errors'];
    	Object_1$2.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console_1$1.warn(`<Prepcomp> was created with unknown prop '${key}'`);
    	});

    	function dynamicselect_options_binding(value) {
    		prepdata.allspecies = value;
    		$$invalidate('prepdata', prepdata);
    	}

    	function dynamicselect_selectval_binding(value_1) {
    		selectedspecies = value_1;
    		$$invalidate('selectedspecies', selectedspecies);
    	}

    	const click_handler = ({ spec }, e) => removeOrganism(spec.id);

    	function input_change_handler() {
    		prepdata.no_enzyme = this.checked;
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	function input_change_handler_1({ enzyme, each_value_7, enzyme_index }) {
    		each_value_7[enzyme_index].checked = this.checked;
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	function param_param_binding(value, { param, each_value_6, each_index_3 }) {
    		each_value_6[each_index_3][1] = value;
    		$$invalidate('Object', Object);
    	}

    	function select_change_handler() {
    		prepdata.quanttype = select_value(this);
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	function textarea_input_handler() {
    		trysamplenames = this.value;
    		$$invalidate('trysamplenames', trysamplenames);
    	}

    	function input_change_handler_2() {
    		prepdata.labelfree_multisample = this.checked;
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	function select_change_handler_1({ channel, each_value, chix }) {
    		each_value[chix].model = select_value(this);
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	const change_handler = ({ channel }, e) => resetNewSampleName(channel);

    	function input_input_handler({ channel, each_value, chix }) {
    		each_value[chix].newprojsample = this.value;
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	const change_handler_1 = ({ chix }, e) => checkNewSample(chix);

    	function select_change_handler_2({ file }) {
    		prepdata.samples[file.associd].model = select_value(this);
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    		$$invalidate('projsamples', projsamples);
    	}

    	const change_handler_2 = ({ file }, e) => resetNewSampleName(prepdata.samples[file.associd]);

    	function input_input_handler_1({ file }) {
    		prepdata.samples[file.associd].newprojsample = this.value;
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    		$$invalidate('projsamples', projsamples);
    	}

    	const change_handler_3 = ({ file }, e) => checkNewSampleLabelfree(file.associd);

    	function select_change_handler_3() {
    		prepdata.labelfree_singlesample.model = select_value(this);
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	const change_handler_4 = (e) => resetNewSampleName(prepdata.labelfree_singlesample);

    	function input_input_handler_2() {
    		prepdata.labelfree_singlesample.newprojsample = this.value;
    		$$invalidate('prepdata', prepdata);
    		$$invalidate('Object', Object);
    	}

    	const change_handler_5 = (e) => checkNewSampleLabelfree(prepdata.labelfree_singlesample);

    	$$self.$set = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    	};

    	$$self.$capture_state = () => {
    		return { errors, preperrors, edited, prepdata, selectedspecies, trysamplenames, labelfree_quant_id, foundNewSamples, stored, $dataset_id, isLabelfree, $datasetFiles };
    	};

    	$$self.$inject_state = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    		if ('preperrors' in $$props) $$invalidate('preperrors', preperrors = $$props.preperrors);
    		if ('edited' in $$props) $$invalidate('edited', edited = $$props.edited);
    		if ('prepdata' in $$props) $$invalidate('prepdata', prepdata = $$props.prepdata);
    		if ('selectedspecies' in $$props) $$invalidate('selectedspecies', selectedspecies = $$props.selectedspecies);
    		if ('trysamplenames' in $$props) $$invalidate('trysamplenames', trysamplenames = $$props.trysamplenames);
    		if ('labelfree_quant_id' in $$props) $$invalidate('labelfree_quant_id', labelfree_quant_id = $$props.labelfree_quant_id);
    		if ('foundNewSamples' in $$props) $$invalidate('foundNewSamples', foundNewSamples = $$props.foundNewSamples);
    		if ('stored' in $$props) $$invalidate('stored', stored = $$props.stored);
    		if ('$dataset_id' in $$props) dataset_id.set($dataset_id);
    		if ('isLabelfree' in $$props) $$invalidate('isLabelfree', isLabelfree = $$props.isLabelfree);
    		if ('$datasetFiles' in $$props) datasetFiles.set($datasetFiles);
    	};

    	let stored, isLabelfree;

    	$$self.$$.update = ($$dirty = { $dataset_id: 1, edited: 1, prepdata: 1, labelfree_quant_id: 1 }) => {
    		if ($$dirty.$dataset_id || $$dirty.edited) { $$invalidate('stored', stored = $dataset_id && !edited); }
    		if ($$dirty.prepdata || $$dirty.labelfree_quant_id) { $$invalidate('isLabelfree', isLabelfree = prepdata.quanttype === labelfree_quant_id); }
    	};

    	return {
    		errors,
    		preperrors,
    		edited,
    		editMade,
    		prepdata,
    		selectedspecies,
    		trysamplenames,
    		foundNewSamples,
    		removeOrganism,
    		addOrganism,
    		checkIfNewSamples,
    		checkNewSampleLabelfree,
    		checkNewSample,
    		parseSampleNames,
    		resetNewSampleName,
    		saveNewSamples,
    		validate,
    		save,
    		fetchData,
    		stored,
    		isLabelfree,
    		Object,
    		$datasetFiles,
    		dynamicselect_options_binding,
    		dynamicselect_selectval_binding,
    		click_handler,
    		input_change_handler,
    		input_change_handler_1,
    		param_param_binding,
    		select_change_handler,
    		textarea_input_handler,
    		input_change_handler_2,
    		select_change_handler_1,
    		change_handler,
    		input_input_handler,
    		change_handler_1,
    		select_change_handler_2,
    		change_handler_2,
    		input_input_handler_1,
    		change_handler_3,
    		select_change_handler_3,
    		change_handler_4,
    		input_input_handler_2,
    		change_handler_5
    	};
    }

    class Prepcomp extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$4, create_fragment$4, safe_not_equal, ["errors", "validate", "save"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "Prepcomp", options, id: create_fragment$4.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.errors === undefined && !('errors' in props)) {
    			console_1$1.warn("<Prepcomp> was created without expected prop 'errors'");
    		}
    		if (ctx.validate === undefined && !('validate' in props)) {
    			console_1$1.warn("<Prepcomp> was created without expected prop 'validate'");
    		}
    		if (ctx.save === undefined && !('save' in props)) {
    			console_1$1.warn("<Prepcomp> was created without expected prop 'save'");
    		}
    	}

    	get errors() {
    		throw new Error("<Prepcomp>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set errors(value) {
    		throw new Error("<Prepcomp>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get validate() {
    		return this.$$.ctx.validate;
    	}

    	set validate(value) {
    		throw new Error("<Prepcomp>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get save() {
    		return this.$$.ctx.save;
    	}

    	set save(value) {
    		throw new Error("<Prepcomp>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/Msdata.svelte generated by Svelte v3.12.1 */

    const file$5 = "src/Msdata.svelte";

    function get_each_context$5(ctx, list, i) {
    	const child_ctx = Object.create(ctx);
    	child_ctx.range = list[i];
    	return child_ctx;
    }

    function get_each_context_1$3(ctx, list, i) {
    	const child_ctx = Object.create(ctx);
    	child_ctx.prefrac = list[i];
    	return child_ctx;
    }

    function get_each_context_2$1(ctx, list, i) {
    	const child_ctx = Object.create(ctx);
    	child_ctx.exp = list[i];
    	return child_ctx;
    }

    // (51:4) {:else}
    function create_else_block_1(ctx) {
    	var t;

    	const block = {
    		c: function create() {
    			t = text("Create new experiment");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(t);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_else_block_1.name, type: "else", source: "(51:4) {:else}", ctx });
    	return block;
    }

    // (49:4) {#if isNewExperiment}
    function create_if_block_4$1(ctx) {
    	var t;

    	const block = {
    		c: function create() {
    			t = text("Existing experiment");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(t);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_4$1.name, type: "if", source: "(49:4) {#if isNewExperiment}", ctx });
    	return block;
    }

    // (59:4) {:else}
    function create_else_block$1(ctx) {
    	var div, select, option, dispose;

    	let each_value_2 = ctx.experiments;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_2.length; i += 1) {
    		each_blocks[i] = create_each_block_2$1(get_each_context_2$1(ctx, each_value_2, i));
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$5, 61, 8, 1512);
    			if (ctx.dsinfo.experiment_id === void 0) add_render_callback(() => ctx.select_change_handler.call(select));
    			add_location(select, file$5, 60, 6, 1440);
    			attr_dev(div, "class", "select");
    			add_location(div, file$5, 59, 4, 1413);

    			dispose = [
    				listen_dev(select, "change", ctx.select_change_handler),
    				listen_dev(select, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.experiment_id);
    		},

    		p: function update(changed, ctx) {
    			if (changed.experiments) {
    				each_value_2 = ctx.experiments;

    				let i;
    				for (i = 0; i < each_value_2.length; i += 1) {
    					const child_ctx = get_each_context_2$1(ctx, each_value_2, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_2$1(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_2.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.experiment_id);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_else_block$1.name, type: "else", source: "(59:4) {:else}", ctx });
    	return block;
    }

    // (57:4) {#if isNewExperiment}
    function create_if_block_3$2(ctx) {
    	var input, dispose;

    	const block = {
    		c: function create() {
    			input = element("input");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "type", "text");
    			attr_dev(input, "placeholder", "Experiment name");
    			add_location(input, file$5, 57, 4, 1274);

    			dispose = [
    				listen_dev(input, "input", ctx.input_input_handler),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, input, anchor);

    			set_input_value(input, ctx.dsinfo.newexperimentname);
    		},

    		p: function update(changed, ctx) {
    			if (changed.dsinfo && (input.value !== ctx.dsinfo.newexperimentname)) set_input_value(input, ctx.dsinfo.newexperimentname);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(input);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_3$2.name, type: "if", source: "(57:4) {#if isNewExperiment}", ctx });
    	return block;
    }

    // (63:8) {#each experiments as exp}
    function create_each_block_2$1(ctx) {
    	var option, t_value = ctx.exp.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.exp.id;
    			option.value = option.__value;
    			add_location(option, file$5, 63, 8, 1608);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.experiments) && t_value !== (t_value = ctx.exp.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.experiments) && option_value_value !== (option_value_value = ctx.exp.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_2$1.name, type: "each", source: "(63:8) {#each experiments as exp}", ctx });
    	return block;
    }

    // (78:8) {#each prefracs as prefrac}
    function create_each_block_1$3(ctx) {
    	var option, t_value = ctx.prefrac.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.prefrac.id;
    			option.value = option.__value;
    			add_location(option, file$5, 78, 8, 1988);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.prefracs) && t_value !== (t_value = ctx.prefrac.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.prefracs) && option_value_value !== (option_value_value = ctx.prefrac.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1$3.name, type: "each", source: "(78:8) {#each prefracs as prefrac}", ctx });
    	return block;
    }

    // (100:28) 
    function create_if_block_2$3(ctx) {
    	var div1, label, t_1, div0, input, input_updating = false, dispose;

    	function input_input_handler_1() {
    		input_updating = true;
    		ctx.input_input_handler_1.call(input);
    	}

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			label = element("label");
    			label.textContent = "Prefractionation length";
    			t_1 = space();
    			div0 = element("div");
    			input = element("input");
    			attr_dev(label, "class", "label");
    			add_location(label, file$5, 101, 2, 2567);
    			attr_dev(input, "type", "number");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "placeholder", "in minutes");
    			add_location(input, file$5, 103, 4, 2648);
    			attr_dev(div0, "class", "control");
    			add_location(div0, file$5, 102, 2, 2622);
    			attr_dev(div1, "class", "field");
    			add_location(div1, file$5, 100, 0, 2545);

    			dispose = [
    				listen_dev(input, "input", input_input_handler_1),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, label);
    			append_dev(div1, t_1);
    			append_dev(div1, div0);
    			append_dev(div0, input);

    			set_input_value(input, ctx.dsinfo.prefrac_length);
    		},

    		p: function update(changed, ctx) {
    			if (!input_updating && changed.dsinfo) set_input_value(input, ctx.dsinfo.prefrac_length);
    			input_updating = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_2$3.name, type: "if", source: "(100:28) ", ctx });
    	return block;
    }

    // (86:0) {#if hiriefselected}
    function create_if_block_1$4(ctx) {
    	var div2, label, t_1, div1, div0, select, option, dispose;

    	let each_value = ctx.hirief_ranges;

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$5(get_each_context$5(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			div2 = element("div");
    			label = element("label");
    			label.textContent = "HiRIEF range";
    			t_1 = space();
    			div1 = element("div");
    			div0 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			attr_dev(label, "class", "label");
    			add_location(label, file$5, 87, 2, 2143);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$5, 91, 8, 2310);
    			if (ctx.dsinfo.hiriefrange === void 0) add_render_callback(() => ctx.select_change_handler_2.call(select));
    			add_location(select, file$5, 90, 6, 2240);
    			attr_dev(div0, "class", "select");
    			add_location(div0, file$5, 89, 4, 2213);
    			attr_dev(div1, "class", "control");
    			add_location(div1, file$5, 88, 2, 2187);
    			attr_dev(div2, "class", "field");
    			add_location(div2, file$5, 86, 0, 2120);

    			dispose = [
    				listen_dev(select, "change", ctx.select_change_handler_2),
    				listen_dev(select, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div2, anchor);
    			append_dev(div2, label);
    			append_dev(div2, t_1);
    			append_dev(div2, div1);
    			append_dev(div1, div0);
    			append_dev(div0, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.hiriefrange);
    		},

    		p: function update(changed, ctx) {
    			if (changed.hirief_ranges) {
    				each_value = ctx.hirief_ranges;

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$5(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block$5(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.hiriefrange);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div2);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1$4.name, type: "if", source: "(86:0) {#if hiriefselected}", ctx });
    	return block;
    }

    // (93:8) {#each hirief_ranges as range}
    function create_each_block$5(ctx) {
    	var option, t_value = ctx.range.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.range.id;
    			option.value = option.__value;
    			add_location(option, file$5, 93, 8, 2410);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.hirief_ranges) && t_value !== (t_value = ctx.range.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.hirief_ranges) && option_value_value !== (option_value_value = ctx.range.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$5.name, type: "each", source: "(93:8) {#each hirief_ranges as range}", ctx });
    	return block;
    }

    // (108:0) {#if dsinfo.prefrac_id}
    function create_if_block$5(ctx) {
    	var div1, label, t_1, div0, input, input_updating = false, dispose;

    	function input_input_handler_2() {
    		input_updating = true;
    		ctx.input_input_handler_2.call(input);
    	}

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			label = element("label");
    			label.textContent = "Fraction amount";
    			t_1 = space();
    			div0 = element("div");
    			input = element("input");
    			attr_dev(label, "class", "label");
    			add_location(label, file$5, 109, 2, 2833);
    			attr_dev(input, "type", "number");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "placeholder", "How many fractions of prefractionation");
    			add_location(input, file$5, 111, 4, 2906);
    			attr_dev(div0, "class", "control");
    			add_location(div0, file$5, 110, 2, 2880);
    			attr_dev(div1, "class", "field");
    			add_location(div1, file$5, 108, 0, 2811);

    			dispose = [
    				listen_dev(input, "input", input_input_handler_2),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, label);
    			append_dev(div1, t_1);
    			append_dev(div1, div0);
    			append_dev(div0, input);

    			set_input_value(input, ctx.dsinfo.prefrac_amount);
    		},

    		p: function update(changed, ctx) {
    			if (!input_updating && changed.dsinfo) set_input_value(input, ctx.dsinfo.prefrac_amount);
    			input_updating = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$5.name, type: "if", source: "(108:0) {#if dsinfo.prefrac_id}", ctx });
    	return block;
    }

    function create_fragment$5(ctx) {
    	var div1, label0, t0, a, t1, div0, t2, div4, label1, t4, div3, div2, select, option, t6, t7, if_block3_anchor, dispose;

    	function select_block_type(changed, ctx) {
    		if (ctx.isNewExperiment) return create_if_block_4$1;
    		return create_else_block_1;
    	}

    	var current_block_type = select_block_type(null, ctx);
    	var if_block0 = current_block_type(ctx);

    	function select_block_type_1(changed, ctx) {
    		if (ctx.isNewExperiment) return create_if_block_3$2;
    		return create_else_block$1;
    	}

    	var current_block_type_1 = select_block_type_1(null, ctx);
    	var if_block1 = current_block_type_1(ctx);

    	let each_value_1 = ctx.prefracs;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks[i] = create_each_block_1$3(get_each_context_1$3(ctx, each_value_1, i));
    	}

    	function select_block_type_2(changed, ctx) {
    		if (ctx.hiriefselected) return create_if_block_1$4;
    		if (ctx.dsinfo.prefrac_id) return create_if_block_2$3;
    	}

    	var current_block_type_2 = select_block_type_2(null, ctx);
    	var if_block2 = current_block_type_2 && current_block_type_2(ctx);

    	var if_block3 = (ctx.dsinfo.prefrac_id) && create_if_block$5(ctx);

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			label0 = element("label");
    			t0 = text("Experiment name\n    ");
    			a = element("a");
    			if_block0.c();
    			t1 = space();
    			div0 = element("div");
    			if_block1.c();
    			t2 = space();
    			div4 = element("div");
    			label1 = element("label");
    			label1.textContent = "Prefractionation";
    			t4 = space();
    			div3 = element("div");
    			div2 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "None";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t6 = space();
    			if (if_block2) if_block2.c();
    			t7 = space();
    			if (if_block3) if_block3.c();
    			if_block3_anchor = empty();
    			attr_dev(a, "class", "button is-danger is-outlined is-small");
    			add_location(a, file$5, 47, 4, 1023);
    			attr_dev(label0, "class", "label");
    			add_location(label0, file$5, 46, 2, 982);
    			attr_dev(div0, "class", "control");
    			add_location(div0, file$5, 55, 2, 1222);
    			attr_dev(div1, "class", "field");
    			add_location(div1, file$5, 45, 0, 960);
    			attr_dev(label1, "class", "label");
    			add_location(label1, file$5, 72, 2, 1743);
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$5, 76, 8, 1913);
    			if (ctx.dsinfo.prefrac_id === void 0) add_render_callback(() => ctx.select_change_handler_1.call(select));
    			add_location(select, file$5, 75, 6, 1844);
    			attr_dev(div2, "class", "select");
    			add_location(div2, file$5, 74, 4, 1817);
    			attr_dev(div3, "class", "control");
    			add_location(div3, file$5, 73, 2, 1791);
    			attr_dev(div4, "class", "field");
    			add_location(div4, file$5, 71, 0, 1721);

    			dispose = [
    				listen_dev(a, "click", ctx.toggle_experiment),
    				listen_dev(select, "change", ctx.select_change_handler_1),
    				listen_dev(select, "change", ctx.editMade)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, label0);
    			append_dev(label0, t0);
    			append_dev(label0, a);
    			if_block0.m(a, null);
    			append_dev(div1, t1);
    			append_dev(div1, div0);
    			if_block1.m(div0, null);
    			insert_dev(target, t2, anchor);
    			insert_dev(target, div4, anchor);
    			append_dev(div4, label1);
    			append_dev(div4, t4);
    			append_dev(div4, div3);
    			append_dev(div3, div2);
    			append_dev(div2, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.prefrac_id);

    			insert_dev(target, t6, anchor);
    			if (if_block2) if_block2.m(target, anchor);
    			insert_dev(target, t7, anchor);
    			if (if_block3) if_block3.m(target, anchor);
    			insert_dev(target, if_block3_anchor, anchor);
    		},

    		p: function update(changed, ctx) {
    			if (current_block_type !== (current_block_type = select_block_type(changed, ctx))) {
    				if_block0.d(1);
    				if_block0 = current_block_type(ctx);
    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(a, null);
    				}
    			}

    			if (current_block_type_1 === (current_block_type_1 = select_block_type_1(changed, ctx)) && if_block1) {
    				if_block1.p(changed, ctx);
    			} else {
    				if_block1.d(1);
    				if_block1 = current_block_type_1(ctx);
    				if (if_block1) {
    					if_block1.c();
    					if_block1.m(div0, null);
    				}
    			}

    			if (changed.prefracs) {
    				each_value_1 = ctx.prefracs;

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1$3(ctx, each_value_1, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_1$3(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_1.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.prefrac_id);

    			if (current_block_type_2 === (current_block_type_2 = select_block_type_2(changed, ctx)) && if_block2) {
    				if_block2.p(changed, ctx);
    			} else {
    				if (if_block2) if_block2.d(1);
    				if_block2 = current_block_type_2 && current_block_type_2(ctx);
    				if (if_block2) {
    					if_block2.c();
    					if_block2.m(t7.parentNode, t7);
    				}
    			}

    			if (ctx.dsinfo.prefrac_id) {
    				if (if_block3) {
    					if_block3.p(changed, ctx);
    				} else {
    					if_block3 = create_if_block$5(ctx);
    					if_block3.c();
    					if_block3.m(if_block3_anchor.parentNode, if_block3_anchor);
    				}
    			} else if (if_block3) {
    				if_block3.d(1);
    				if_block3 = null;
    			}
    		},

    		i: noop,
    		o: noop,

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			if_block0.d();
    			if_block1.d();

    			if (detaching) {
    				detach_dev(t2);
    				detach_dev(div4);
    			}

    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(t6);
    			}

    			if (if_block2) if_block2.d(detaching);

    			if (detaching) {
    				detach_dev(t7);
    			}

    			if (if_block3) if_block3.d(detaching);

    			if (detaching) {
    				detach_dev(if_block3_anchor);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$5.name, type: "component", source: "", ctx });
    	return block;
    }

    function instance$5($$self, $$props, $$invalidate) {
    	const dispatch = createEventDispatcher();

    // props
    let { dsinfo, experiments, hirief_ranges, prefracs, isNewExperiment } = $$props;

    let errors = [];

    function toggle_experiment() {
      $$invalidate('isNewExperiment', isNewExperiment = isNewExperiment === false);
    }

    function editMade() {
      dispatch('edited');
    }

    function validate() {
      errors = [];
    	if (hiriefselected && !dsinfo.hiriefrange) {
    		errors.push('HiRIEF range is required');
    	}
    	else if (!hiriefselected && dsinfo.prefrac_id && !dsinfo.prefrac_length) {
    		errors.push('Prefractionation length is required');
    	}
    	if (dsinfo.prefrac_id && !dsinfo.prefrac_amount) {
    		errors.push('Prefractionation fraction amount is required');
    	}
      return errors;
    }

    	const writable_props = ['dsinfo', 'experiments', 'hirief_ranges', 'prefracs', 'isNewExperiment'];
    	Object.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console.warn(`<Msdata> was created with unknown prop '${key}'`);
    	});

    	function input_input_handler() {
    		dsinfo.newexperimentname = this.value;
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('experiments', experiments);
    	}

    	function select_change_handler() {
    		dsinfo.experiment_id = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('experiments', experiments);
    	}

    	function select_change_handler_1() {
    		dsinfo.prefrac_id = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('experiments', experiments);
    	}

    	function select_change_handler_2() {
    		dsinfo.hiriefrange = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('experiments', experiments);
    	}

    	function input_input_handler_1() {
    		dsinfo.prefrac_length = to_number(this.value);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('experiments', experiments);
    	}

    	function input_input_handler_2() {
    		dsinfo.prefrac_amount = to_number(this.value);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('experiments', experiments);
    	}

    	$$self.$set = $$props => {
    		if ('dsinfo' in $$props) $$invalidate('dsinfo', dsinfo = $$props.dsinfo);
    		if ('experiments' in $$props) $$invalidate('experiments', experiments = $$props.experiments);
    		if ('hirief_ranges' in $$props) $$invalidate('hirief_ranges', hirief_ranges = $$props.hirief_ranges);
    		if ('prefracs' in $$props) $$invalidate('prefracs', prefracs = $$props.prefracs);
    		if ('isNewExperiment' in $$props) $$invalidate('isNewExperiment', isNewExperiment = $$props.isNewExperiment);
    	};

    	$$self.$capture_state = () => {
    		return { dsinfo, experiments, hirief_ranges, prefracs, isNewExperiment, errors, hiriefselected };
    	};

    	$$self.$inject_state = $$props => {
    		if ('dsinfo' in $$props) $$invalidate('dsinfo', dsinfo = $$props.dsinfo);
    		if ('experiments' in $$props) $$invalidate('experiments', experiments = $$props.experiments);
    		if ('hirief_ranges' in $$props) $$invalidate('hirief_ranges', hirief_ranges = $$props.hirief_ranges);
    		if ('prefracs' in $$props) $$invalidate('prefracs', prefracs = $$props.prefracs);
    		if ('isNewExperiment' in $$props) $$invalidate('isNewExperiment', isNewExperiment = $$props.isNewExperiment);
    		if ('errors' in $$props) errors = $$props.errors;
    		if ('hiriefselected' in $$props) $$invalidate('hiriefselected', hiriefselected = $$props.hiriefselected);
    	};

    	let hiriefselected;

    	$$self.$$.update = ($$dirty = { prefracs: 1, dsinfo: 1 }) => {
    		if ($$dirty.prefracs || $$dirty.dsinfo) { $$invalidate('hiriefselected', hiriefselected = prefracs.some(pf => pf.id == dsinfo.prefrac_id && pf.name.toLowerCase().indexOf('hirief') > -1)); }
    	};

    	return {
    		dsinfo,
    		experiments,
    		hirief_ranges,
    		prefracs,
    		isNewExperiment,
    		toggle_experiment,
    		editMade,
    		validate,
    		hiriefselected,
    		input_input_handler,
    		select_change_handler,
    		select_change_handler_1,
    		select_change_handler_2,
    		input_input_handler_1,
    		input_input_handler_2
    	};
    }

    class Msdata extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$5, create_fragment$5, safe_not_equal, ["dsinfo", "experiments", "hirief_ranges", "prefracs", "isNewExperiment", "validate"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "Msdata", options, id: create_fragment$5.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.dsinfo === undefined && !('dsinfo' in props)) {
    			console.warn("<Msdata> was created without expected prop 'dsinfo'");
    		}
    		if (ctx.experiments === undefined && !('experiments' in props)) {
    			console.warn("<Msdata> was created without expected prop 'experiments'");
    		}
    		if (ctx.hirief_ranges === undefined && !('hirief_ranges' in props)) {
    			console.warn("<Msdata> was created without expected prop 'hirief_ranges'");
    		}
    		if (ctx.prefracs === undefined && !('prefracs' in props)) {
    			console.warn("<Msdata> was created without expected prop 'prefracs'");
    		}
    		if (ctx.isNewExperiment === undefined && !('isNewExperiment' in props)) {
    			console.warn("<Msdata> was created without expected prop 'isNewExperiment'");
    		}
    		if (ctx.validate === undefined && !('validate' in props)) {
    			console.warn("<Msdata> was created without expected prop 'validate'");
    		}
    	}

    	get dsinfo() {
    		throw new Error("<Msdata>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set dsinfo(value) {
    		throw new Error("<Msdata>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get experiments() {
    		throw new Error("<Msdata>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set experiments(value) {
    		throw new Error("<Msdata>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get hirief_ranges() {
    		throw new Error("<Msdata>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set hirief_ranges(value) {
    		throw new Error("<Msdata>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get prefracs() {
    		throw new Error("<Msdata>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set prefracs(value) {
    		throw new Error("<Msdata>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get isNewExperiment() {
    		throw new Error("<Msdata>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set isNewExperiment(value) {
    		throw new Error("<Msdata>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	get validate() {
    		return this.$$.ctx.validate;
    	}

    	set validate(value) {
    		throw new Error("<Msdata>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/LCheck.svelte generated by Svelte v3.12.1 */
    const { Object: Object_1$3, console: console_1$2 } = globals;

    const file$6 = "src/LCheck.svelte";

    function get_each_context$6(ctx, list, i) {
    	const child_ctx = Object_1$3.create(ctx);
    	child_ctx.file = list[i];
    	return child_ctx;
    }

    function get_each_context_1$4(ctx, list, i) {
    	const child_ctx = Object_1$3.create(ctx);
    	child_ctx.quant = list[i];
    	return child_ctx;
    }

    // (129:19) 
    function create_if_block_6$1(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-edit");
    			add_location(i, file$6, 129, 2, 3518);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_6$1.name, type: "if", source: "(129:19) ", ctx });
    	return block;
    }

    // (127:2) {#if stored}
    function create_if_block_5$1(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-check-circle");
    			add_location(i, file$6, 127, 2, 3455);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_5$1.name, type: "if", source: "(127:2) {#if stored}", ctx });
    	return block;
    }

    // (145:8) {#each Object.values(lcdata.quants) as quant}
    function create_each_block_1$4(ctx) {
    	var option, t_value = ctx.quant.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.quant.id;
    			option.value = option.__value;
    			add_location(option, file$6, 145, 8, 4147);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.lcdata) && t_value !== (t_value = ctx.quant.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.lcdata) && option_value_value !== (option_value_value = ctx.quant.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1$4.name, type: "each", source: "(145:8) {#each Object.values(lcdata.quants) as quant}", ctx });
    	return block;
    }

    // (155:0) {:else}
    function create_else_block$2(ctx) {
    	var a;

    	const block = {
    		c: function create() {
    			a = element("a");
    			a.textContent = "Save new samples";
    			attr_dev(a, "class", "button is-danger is-small is-pulled-right");
    			attr_dev(a, "disabled", "");
    			add_location(a, file$6, 155, 0, 4384);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, a, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(a);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_else_block$2.name, type: "else", source: "(155:0) {:else}", ctx });
    	return block;
    }

    // (153:0) {#if foundNewSamples}
    function create_if_block_4$2(ctx) {
    	var a, dispose;

    	const block = {
    		c: function create() {
    			a = element("a");
    			a.textContent = "Save new samples";
    			attr_dev(a, "class", "button is-danger is-small is-pulled-right");
    			add_location(a, file$6, 153, 0, 4276);
    			dispose = listen_dev(a, "click", ctx.saveNewSamples);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, a, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(a);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_4$2.name, type: "if", source: "(153:0) {#if foundNewSamples}", ctx });
    	return block;
    }

    // (166:2) {#if Object.keys(lcdata.samples).length}
    function create_if_block$6(ctx) {
    	var tbody, current;

    	let each_value = ctx.Object.values(ctx.$datasetFiles);

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$6(get_each_context$6(ctx, each_value, i));
    	}

    	const out = i => transition_out(each_blocks[i], 1, 1, () => {
    		each_blocks[i] = null;
    	});

    	const block = {
    		c: function create() {
    			tbody = element("tbody");

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			add_location(tbody, file$6, 166, 2, 4640);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tbody, anchor);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(tbody, null);
    			}

    			current = true;
    		},

    		p: function update(changed, ctx) {
    			if (changed.lcdata || changed.Object || changed.$datasetFiles || changed.projsamples) {
    				each_value = ctx.Object.values(ctx.$datasetFiles);

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$6(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    						transition_in(each_blocks[i], 1);
    					} else {
    						each_blocks[i] = create_each_block$6(child_ctx);
    						each_blocks[i].c();
    						transition_in(each_blocks[i], 1);
    						each_blocks[i].m(tbody, null);
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
    			if (detaching) {
    				detach_dev(tbody);
    			}

    			destroy_each(each_blocks, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$6.name, type: "if", source: "(166:2) {#if Object.keys(lcdata.samples).length}", ctx });
    	return block;
    }

    // (172:10) {#if lcdata.samples[file.associd].newprojsample}
    function create_if_block_3$3(ctx) {
    	var span, i;

    	const block = {
    		c: function create() {
    			span = element("span");
    			i = element("i");
    			attr_dev(i, "class", "fas fa-asterisk");
    			add_location(i, file$6, 172, 45, 4851);
    			attr_dev(span, "class", "icon has-text-danger");
    			add_location(span, file$6, 172, 10, 4816);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, i);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(span);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_3$3.name, type: "if", source: "(172:10) {#if lcdata.samples[file.associd].newprojsample}", ctx });
    	return block;
    }

    // (185:12) {#if lcdata.quanttype}
    function create_if_block_1$5(ctx) {
    	var updating_intext, updating_fixedoptions, updating_fixedorder, updating_selectval, t, if_block_anchor, current;

    	function dynamicselect_intext_binding_1(value) {
    		ctx.dynamicselect_intext_binding_1.call(null, value, ctx);
    		updating_intext = true;
    		add_flush_callback(() => updating_intext = false);
    	}

    	function dynamicselect_fixedoptions_binding(value_1) {
    		ctx.dynamicselect_fixedoptions_binding.call(null, value_1);
    		updating_fixedoptions = true;
    		add_flush_callback(() => updating_fixedoptions = false);
    	}

    	function dynamicselect_fixedorder_binding(value_2) {
    		ctx.dynamicselect_fixedorder_binding.call(null, value_2);
    		updating_fixedorder = true;
    		add_flush_callback(() => updating_fixedorder = false);
    	}

    	function dynamicselect_selectval_binding_1(value_3) {
    		ctx.dynamicselect_selectval_binding_1.call(null, value_3, ctx);
    		updating_selectval = true;
    		add_flush_callback(() => updating_selectval = false);
    	}

    	function selectedvalue_handler(...args) {
    		return ctx.selectedvalue_handler(ctx, ...args);
    	}

    	function illegalvalue_handler(...args) {
    		return ctx.illegalvalue_handler(ctx, ...args);
    	}

    	let dynamicselect_props = { niceName: func_1 };
    	if (ctx.lcdata.samples[ctx.file.associd].channelname !== void 0) {
    		dynamicselect_props.intext = ctx.lcdata.samples[ctx.file.associd].channelname;
    	}
    	if (ctx.lcdata.quants[ctx.lcdata.quanttype].chans !== void 0) {
    		dynamicselect_props.fixedoptions = ctx.lcdata.quants[ctx.lcdata.quanttype].chans;
    	}
    	if (ctx.lcdata.quants[ctx.lcdata.quanttype].chanorder !== void 0) {
    		dynamicselect_props.fixedorder = ctx.lcdata.quants[ctx.lcdata.quanttype].chanorder;
    	}
    	if (ctx.lcdata.samples[ctx.file.associd].channel !== void 0) {
    		dynamicselect_props.selectval = ctx.lcdata.samples[ctx.file.associd].channel;
    	}
    	var dynamicselect = new DynamicSelect({
    		props: dynamicselect_props,
    		$$inline: true
    	});

    	binding_callbacks.push(() => bind(dynamicselect, 'intext', dynamicselect_intext_binding_1));
    	binding_callbacks.push(() => bind(dynamicselect, 'fixedoptions', dynamicselect_fixedoptions_binding));
    	binding_callbacks.push(() => bind(dynamicselect, 'fixedorder', dynamicselect_fixedorder_binding));
    	binding_callbacks.push(() => bind(dynamicselect, 'selectval', dynamicselect_selectval_binding_1));
    	dynamicselect.$on("selectedvalue", selectedvalue_handler);
    	dynamicselect.$on("illegalvalue", illegalvalue_handler);

    	var if_block = (ctx.lcdata.samples[ctx.file.associd].badChannel) && create_if_block_2$4(ctx);

    	const block = {
    		c: function create() {
    			dynamicselect.$$.fragment.c();
    			t = space();
    			if (if_block) if_block.c();
    			if_block_anchor = empty();
    		},

    		m: function mount(target, anchor) {
    			mount_component(dynamicselect, target, anchor);
    			insert_dev(target, t, anchor);
    			if (if_block) if_block.m(target, anchor);
    			insert_dev(target, if_block_anchor, anchor);
    			current = true;
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			var dynamicselect_changes = {};
    			if (!updating_intext && changed.lcdata || changed.Object || changed.$datasetFiles) {
    				dynamicselect_changes.intext = ctx.lcdata.samples[ctx.file.associd].channelname;
    			}
    			if (!updating_fixedoptions && changed.lcdata) {
    				dynamicselect_changes.fixedoptions = ctx.lcdata.quants[ctx.lcdata.quanttype].chans;
    			}
    			if (!updating_fixedorder && changed.lcdata) {
    				dynamicselect_changes.fixedorder = ctx.lcdata.quants[ctx.lcdata.quanttype].chanorder;
    			}
    			if (!updating_selectval && changed.lcdata || changed.Object || changed.$datasetFiles) {
    				dynamicselect_changes.selectval = ctx.lcdata.samples[ctx.file.associd].channel;
    			}
    			dynamicselect.$set(dynamicselect_changes);

    			if (ctx.lcdata.samples[ctx.file.associd].badChannel) {
    				if (!if_block) {
    					if_block = create_if_block_2$4(ctx);
    					if_block.c();
    					if_block.m(if_block_anchor.parentNode, if_block_anchor);
    				}
    			} else if (if_block) {
    				if_block.d(1);
    				if_block = null;
    			}
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(dynamicselect.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(dynamicselect.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			destroy_component(dynamicselect, detaching);

    			if (detaching) {
    				detach_dev(t);
    			}

    			if (if_block) if_block.d(detaching);

    			if (detaching) {
    				detach_dev(if_block_anchor);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1$5.name, type: "if", source: "(185:12) {#if lcdata.quanttype}", ctx });
    	return block;
    }

    // (188:12) {#if lcdata.samples[file.associd].badChannel}
    function create_if_block_2$4(ctx) {
    	var span, i;

    	const block = {
    		c: function create() {
    			span = element("span");
    			i = element("i");
    			attr_dev(i, "class", "fas fa-asterisk");
    			add_location(i, file$6, 189, 10, 6011);
    			attr_dev(span, "class", "icon is-left has-text-danger");
    			add_location(span, file$6, 188, 8, 5957);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, i);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(span);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_2$4.name, type: "if", source: "(188:12) {#if lcdata.samples[file.associd].badChannel}", ctx });
    	return block;
    }

    // (168:4) {#each Object.values($datasetFiles) as file}
    function create_each_block$6(ctx) {
    	var tr, td0, label, t0, t1_value = ctx.file.name + "", t1, t2, div0, updating_intext, updating_unknowninput, updating_selectval, t3, td1, div2, div1, p, p_class_value, t4, current;

    	var if_block0 = (ctx.lcdata.samples[ctx.file.associd].newprojsample) && create_if_block_3$3(ctx);

    	function dynamicselect_intext_binding(value) {
    		ctx.dynamicselect_intext_binding.call(null, value, ctx);
    		updating_intext = true;
    		add_flush_callback(() => updating_intext = false);
    	}

    	function dynamicselect_unknowninput_binding(value_1) {
    		ctx.dynamicselect_unknowninput_binding.call(null, value_1, ctx);
    		updating_unknowninput = true;
    		add_flush_callback(() => updating_unknowninput = false);
    	}

    	function dynamicselect_selectval_binding(value_2) {
    		ctx.dynamicselect_selectval_binding.call(null, value_2, ctx);
    		updating_selectval = true;
    		add_flush_callback(() => updating_selectval = false);
    	}

    	function newvalue_handler(...args) {
    		return ctx.newvalue_handler(ctx, ...args);
    	}

    	let dynamicselect_props = {
    		fixedoptions: projsamples,
    		niceName: func
    	};
    	if (ctx.lcdata.samples[ctx.file.associd].samplename !== void 0) {
    		dynamicselect_props.intext = ctx.lcdata.samples[ctx.file.associd].samplename;
    	}
    	if (ctx.lcdata.samples[ctx.file.associd].newprojsample !== void 0) {
    		dynamicselect_props.unknowninput = ctx.lcdata.samples[ctx.file.associd].newprojsample;
    	}
    	if (ctx.lcdata.samples[ctx.file.associd].sample !== void 0) {
    		dynamicselect_props.selectval = ctx.lcdata.samples[ctx.file.associd].sample;
    	}
    	var dynamicselect = new DynamicSelect({
    		props: dynamicselect_props,
    		$$inline: true
    	});

    	binding_callbacks.push(() => bind(dynamicselect, 'intext', dynamicselect_intext_binding));
    	binding_callbacks.push(() => bind(dynamicselect, 'unknowninput', dynamicselect_unknowninput_binding));
    	binding_callbacks.push(() => bind(dynamicselect, 'selectval', dynamicselect_selectval_binding));
    	dynamicselect.$on("selectedvalue", ctx.editMade);
    	dynamicselect.$on("newvalue", newvalue_handler);

    	var if_block1 = (ctx.lcdata.quanttype) && create_if_block_1$5(ctx);

    	const block = {
    		c: function create() {
    			tr = element("tr");
    			td0 = element("td");
    			label = element("label");
    			if (if_block0) if_block0.c();
    			t0 = space();
    			t1 = text(t1_value);
    			t2 = space();
    			div0 = element("div");
    			dynamicselect.$$.fragment.c();
    			t3 = space();
    			td1 = element("td");
    			div2 = element("div");
    			div1 = element("div");
    			p = element("p");
    			if (if_block1) if_block1.c();
    			t4 = space();
    			attr_dev(label, "class", "label");
    			add_location(label, file$6, 170, 8, 4725);
    			attr_dev(div0, "class", "field");
    			add_location(div0, file$6, 176, 8, 4953);
    			add_location(td0, file$6, 169, 6, 4712);
    			attr_dev(p, "class", p_class_value = ctx.lcdata.samples[ctx.file.associd].badChannel ? 'control has-icons-left': '');
    			add_location(p, file$6, 183, 12, 5398);
    			attr_dev(div1, "class", "control");
    			add_location(div1, file$6, 182, 10, 5364);
    			attr_dev(div2, "class", "field");
    			add_location(div2, file$6, 181, 8, 5334);
    			add_location(td1, file$6, 180, 6, 5321);
    			add_location(tr, file$6, 168, 4, 4701);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tr, anchor);
    			append_dev(tr, td0);
    			append_dev(td0, label);
    			if (if_block0) if_block0.m(label, null);
    			append_dev(label, t0);
    			append_dev(label, t1);
    			append_dev(td0, t2);
    			append_dev(td0, div0);
    			mount_component(dynamicselect, div0, null);
    			append_dev(tr, t3);
    			append_dev(tr, td1);
    			append_dev(td1, div2);
    			append_dev(div2, div1);
    			append_dev(div1, p);
    			if (if_block1) if_block1.m(p, null);
    			append_dev(tr, t4);
    			current = true;
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if (ctx.lcdata.samples[ctx.file.associd].newprojsample) {
    				if (!if_block0) {
    					if_block0 = create_if_block_3$3(ctx);
    					if_block0.c();
    					if_block0.m(label, t0);
    				}
    			} else if (if_block0) {
    				if_block0.d(1);
    				if_block0 = null;
    			}

    			if ((!current || changed.$datasetFiles) && t1_value !== (t1_value = ctx.file.name + "")) {
    				set_data_dev(t1, t1_value);
    			}

    			var dynamicselect_changes = {};
    			if (changed.projsamples) dynamicselect_changes.fixedoptions = projsamples;
    			if (!updating_intext && changed.lcdata || changed.Object || changed.$datasetFiles) {
    				dynamicselect_changes.intext = ctx.lcdata.samples[ctx.file.associd].samplename;
    			}
    			if (!updating_unknowninput && changed.lcdata || changed.Object || changed.$datasetFiles) {
    				dynamicselect_changes.unknowninput = ctx.lcdata.samples[ctx.file.associd].newprojsample;
    			}
    			if (!updating_selectval && changed.lcdata || changed.Object || changed.$datasetFiles) {
    				dynamicselect_changes.selectval = ctx.lcdata.samples[ctx.file.associd].sample;
    			}
    			dynamicselect.$set(dynamicselect_changes);

    			if (ctx.lcdata.quanttype) {
    				if (if_block1) {
    					if_block1.p(changed, ctx);
    					transition_in(if_block1, 1);
    				} else {
    					if_block1 = create_if_block_1$5(ctx);
    					if_block1.c();
    					transition_in(if_block1, 1);
    					if_block1.m(p, null);
    				}
    			} else if (if_block1) {
    				group_outros();
    				transition_out(if_block1, 1, 1, () => {
    					if_block1 = null;
    				});
    				check_outros();
    			}

    			if ((!current || changed.lcdata || changed.$datasetFiles) && p_class_value !== (p_class_value = ctx.lcdata.samples[ctx.file.associd].badChannel ? 'control has-icons-left': '')) {
    				attr_dev(p, "class", p_class_value);
    			}
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(dynamicselect.$$.fragment, local);

    			transition_in(if_block1);
    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(dynamicselect.$$.fragment, local);
    			transition_out(if_block1);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(tr);
    			}

    			if (if_block0) if_block0.d();

    			destroy_component(dynamicselect);

    			if (if_block1) if_block1.d();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$6.name, type: "each", source: "(168:4) {#each Object.values($datasetFiles) as file}", ctx });
    	return block;
    }

    function create_fragment$6(ctx) {
    	var h5, t0, button0, t1, button0_disabled_value, t2, button1, t3, button1_disabled_value, t4, t5, div2, label, t7, div1, div0, select, option, t9, t10, table, thead, tr, th0, t12, th1, t14, show_if = ctx.Object.keys(ctx.lcdata.samples).length, current, dispose;

    	function select_block_type(changed, ctx) {
    		if (ctx.stored) return create_if_block_5$1;
    		if (ctx.edited) return create_if_block_6$1;
    	}

    	var current_block_type = select_block_type(null, ctx);
    	var if_block0 = current_block_type && current_block_type(ctx);

    	var errornotif = new ErrorNotif({
    		props: { errors: ctx.lcerrors },
    		$$inline: true
    	});

    	let each_value_1 = ctx.Object.values(ctx.lcdata.quants);

    	let each_blocks = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks[i] = create_each_block_1$4(get_each_context_1$4(ctx, each_value_1, i));
    	}

    	function select_block_type_1(changed, ctx) {
    		if (ctx.foundNewSamples) return create_if_block_4$2;
    		return create_else_block$2;
    	}

    	var current_block_type_1 = select_block_type_1(null, ctx);
    	var if_block1 = current_block_type_1(ctx);

    	var if_block2 = (show_if) && create_if_block$6(ctx);

    	const block = {
    		c: function create() {
    			h5 = element("h5");
    			if (if_block0) if_block0.c();
    			t0 = text("\n  Label check\n  ");
    			button0 = element("button");
    			t1 = text("Save");
    			t2 = space();
    			button1 = element("button");
    			t3 = text("Revert");
    			t4 = space();
    			errornotif.$$.fragment.c();
    			t5 = space();
    			div2 = element("div");
    			label = element("label");
    			label.textContent = "Quant type";
    			t7 = space();
    			div1 = element("div");
    			div0 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t9 = space();
    			if_block1.c();
    			t10 = space();
    			table = element("table");
    			thead = element("thead");
    			tr = element("tr");
    			th0 = element("th");
    			th0.textContent = "Sample";
    			t12 = space();
    			th1 = element("th");
    			th1.textContent = "Channel";
    			t14 = space();
    			if (if_block2) if_block2.c();
    			attr_dev(button0, "class", "button is-small is-danger has-text-weight-bold");
    			button0.disabled = button0_disabled_value = !ctx.edited;
    			add_location(button0, file$6, 132, 2, 3575);
    			attr_dev(button1, "class", "button is-small is-info has-text-weight-bold");
    			button1.disabled = button1_disabled_value = !ctx.edited;
    			add_location(button1, file$6, 133, 2, 3689);
    			attr_dev(h5, "id", "labelcheck");
    			attr_dev(h5, "class", "has-text-primary title is-5");
    			add_location(h5, file$6, 125, 0, 3381);
    			attr_dev(label, "class", "label");
    			add_location(label, file$6, 139, 2, 3869);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$6, 143, 8, 4032);
    			if (ctx.lcdata.quanttype === void 0) add_render_callback(() => ctx.select_change_handler.call(select));
    			add_location(select, file$6, 142, 6, 3964);
    			attr_dev(div0, "class", "select");
    			add_location(div0, file$6, 141, 4, 3937);
    			attr_dev(div1, "class", "control");
    			add_location(div1, file$6, 140, 2, 3911);
    			attr_dev(div2, "class", "field");
    			add_location(div2, file$6, 138, 0, 3847);
    			add_location(th0, file$6, 161, 6, 4535);
    			add_location(th1, file$6, 162, 6, 4557);
    			add_location(tr, file$6, 160, 4, 4524);
    			add_location(thead, file$6, 159, 2, 4512);
    			attr_dev(table, "class", "table is-fullwidth");
    			add_location(table, file$6, 158, 0, 4474);

    			dispose = [
    				listen_dev(button0, "click", ctx.save),
    				listen_dev(button1, "click", ctx.fetchData),
    				listen_dev(select, "change", ctx.select_change_handler),
    				listen_dev(select, "change", ctx.editMade)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, h5, anchor);
    			if (if_block0) if_block0.m(h5, null);
    			append_dev(h5, t0);
    			append_dev(h5, button0);
    			append_dev(button0, t1);
    			append_dev(h5, t2);
    			append_dev(h5, button1);
    			append_dev(button1, t3);
    			insert_dev(target, t4, anchor);
    			mount_component(errornotif, target, anchor);
    			insert_dev(target, t5, anchor);
    			insert_dev(target, div2, anchor);
    			append_dev(div2, label);
    			append_dev(div2, t7);
    			append_dev(div2, div1);
    			append_dev(div1, div0);
    			append_dev(div0, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.lcdata.quanttype);

    			insert_dev(target, t9, anchor);
    			if_block1.m(target, anchor);
    			insert_dev(target, t10, anchor);
    			insert_dev(target, table, anchor);
    			append_dev(table, thead);
    			append_dev(thead, tr);
    			append_dev(tr, th0);
    			append_dev(tr, t12);
    			append_dev(tr, th1);
    			append_dev(table, t14);
    			if (if_block2) if_block2.m(table, null);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			if (current_block_type !== (current_block_type = select_block_type(changed, ctx))) {
    				if (if_block0) if_block0.d(1);
    				if_block0 = current_block_type && current_block_type(ctx);
    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(h5, t0);
    				}
    			}

    			if ((!current || changed.edited) && button0_disabled_value !== (button0_disabled_value = !ctx.edited)) {
    				prop_dev(button0, "disabled", button0_disabled_value);
    			}

    			if ((!current || changed.edited) && button1_disabled_value !== (button1_disabled_value = !ctx.edited)) {
    				prop_dev(button1, "disabled", button1_disabled_value);
    			}

    			var errornotif_changes = {};
    			if (changed.lcerrors) errornotif_changes.errors = ctx.lcerrors;
    			errornotif.$set(errornotif_changes);

    			if (changed.Object || changed.lcdata) {
    				each_value_1 = ctx.Object.values(ctx.lcdata.quants);

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1$4(ctx, each_value_1, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_1$4(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_1.length;
    			}

    			if (changed.lcdata) select_option(select, ctx.lcdata.quanttype);

    			if (current_block_type_1 !== (current_block_type_1 = select_block_type_1(changed, ctx))) {
    				if_block1.d(1);
    				if_block1 = current_block_type_1(ctx);
    				if (if_block1) {
    					if_block1.c();
    					if_block1.m(t10.parentNode, t10);
    				}
    			}

    			if (changed.lcdata) show_if = ctx.Object.keys(ctx.lcdata.samples).length;

    			if (show_if) {
    				if (if_block2) {
    					if_block2.p(changed, ctx);
    					transition_in(if_block2, 1);
    				} else {
    					if_block2 = create_if_block$6(ctx);
    					if_block2.c();
    					transition_in(if_block2, 1);
    					if_block2.m(table, null);
    				}
    			} else if (if_block2) {
    				group_outros();
    				transition_out(if_block2, 1, 1, () => {
    					if_block2 = null;
    				});
    				check_outros();
    			}
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(errornotif.$$.fragment, local);

    			transition_in(if_block2);
    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(errornotif.$$.fragment, local);
    			transition_out(if_block2);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(h5);
    			}

    			if (if_block0) if_block0.d();

    			if (detaching) {
    				detach_dev(t4);
    			}

    			destroy_component(errornotif, detaching);

    			if (detaching) {
    				detach_dev(t5);
    				detach_dev(div2);
    			}

    			destroy_each(each_blocks, detaching);

    			if (detaching) {
    				detach_dev(t9);
    			}

    			if_block1.d(detaching);

    			if (detaching) {
    				detach_dev(t10);
    				detach_dev(table);
    			}

    			if (if_block2) if_block2.d();
    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$6.name, type: "component", source: "", ctx });
    	return block;
    }

    const func = (x) => x.name;

    const func_1 = (x) => x.name;

    function instance$6($$self, $$props, $$invalidate) {
    	let $dataset_id, $datasetFiles;

    	validate_store(dataset_id, 'dataset_id');
    	component_subscribe($$self, dataset_id, $$value => { $dataset_id = $$value; $$invalidate('$dataset_id', $dataset_id); });
    	validate_store(datasetFiles, 'datasetFiles');
    	component_subscribe($$self, datasetFiles, $$value => { $datasetFiles = $$value; $$invalidate('$datasetFiles', $datasetFiles); });

    	

    let { errors } = $$props;

    let lcerrors = [];
    let channelError = {};

    let lcdata = {
      quants: {},
      quanttype: '',
      samples: {},
    };
    let edited = false;


    function editMade() {
      $$invalidate('edited', edited = true);
    }

    function okChannel(fid) {
      $$invalidate('lcdata', lcdata.samples[fid].badChannel = false, lcdata);
      editMade();
    }

    function badChannel(fid) {
      console.log('bad ch');
      console.log(fid);
      $$invalidate('lcdata', lcdata.samples[fid].badChannel = true, lcdata);
    }


    async function doSampleSave(ch_or_samfn, ix) { 
      /* Saves a new sample name to the project on backend */
      let postdata = {
        dataset_id: $dataset_id, 
        samplename: ch_or_samfn.newprojsample
      };
      let url = '/datasets/save/projsample/';
      const response = await postJSON(url, postdata);
      // just add the latest projsample, do not just assign the whole projsamples dict, async problems!
      projsamples[response.psid] = response.psname;
      return [response.psid, ix];
    }

    async function saveNewSamples() {
      /* Goes through each of the new sample names and */
      let saves = [];
      Object.entries(lcdata.samples).filter(x => x[1].newprojsample).forEach(function(samfn) {
        saves.push(doSampleSave(samfn[1], samfn[0]));
      });
      for (let item of saves) {
        let [psid, associd] = await item;
        $$invalidate('lcdata', lcdata.samples[associd].newprojsample = '', lcdata);
        $$invalidate('lcdata', lcdata.samples[associd].sample = psid, lcdata);
      }
    }

    function checkNewSample(file) {
      /* Checks if entered sample is found in project or if it is a new sample */
      let uppername = lcdata.samples[file.associd].newprojsample.trim().toUpperCase();
      let found = Object.entries(projsamples).filter(x=>x[1].name.toUpperCase() == uppername).map(x=>x[0])[0];
      if (found) {
        $$invalidate('lcdata', lcdata.samples[file.associd].sample = parseInt(found), lcdata);
        $$invalidate('lcdata', lcdata.samples[file.associd].newprojsample = '', lcdata);
      }
      editMade();
    }

    function validate() {
      let comperrors = [];
    	if (!lcdata.quanttype) {
    		comperrors.push('Quant type selection is required');
    	}
      for (let fn of Object.values($datasetFiles)) {
        if (!lcdata.samples[fn.associd].sample) {
          comperrors.push('Sample name for each file/channel is required');
        }
        if (!lcdata.samples[fn.associd].channel) {
          comperrors.push('Channel for each file/sample is required');
        }
      }	
      return comperrors;
    }

    async function save() {
      $$invalidate('errors', errors = validate());
      if (!Object.keys($datasetFiles).length) {
        $$invalidate('lcerrors', lcerrors = [...lcerrors, 'Add files before saving data']);
      }
      if (errors.length === 0) { 
        let postdata = {
          dataset_id: $dataset_id,
          quanttype: lcdata.quanttype,
          samples: lcdata.samples,
          filenames: Object.values($datasetFiles),
        };
        console.log(postdata);
        const url = '/datasets/save/labelcheck/';
        const response = await postJSON(url, postdata);
        fetchData();
      }
    }

    async function fetchData() {
      let url = '/datasets/show/labelcheck/';
      url = $dataset_id ? url + $dataset_id : url;
    	const response = await getJSON(url);
      for (let [key, val] of Object.entries(response)) { $$invalidate('lcdata', lcdata[key] = val, lcdata); }
      $$invalidate('edited', edited = false);
    }

    onMount(async() => {
      await fetchData();
    });

    	const writable_props = ['errors'];
    	Object_1$3.keys($$props).forEach(key => {
    		if (!writable_props.includes(key) && !key.startsWith('$$')) console_1$2.warn(`<LCheck> was created with unknown prop '${key}'`);
    	});

    	function select_change_handler() {
    		lcdata.quanttype = select_value(this);
    		$$invalidate('lcdata', lcdata);
    		$$invalidate('Object', Object);
    	}

    	function dynamicselect_intext_binding(value, { file }) {
    		lcdata.samples[file.associd].samplename = value;
    		$$invalidate('lcdata', lcdata);
    	}

    	function dynamicselect_unknowninput_binding(value_1, { file }) {
    		lcdata.samples[file.associd].newprojsample = value_1;
    		$$invalidate('lcdata', lcdata);
    	}

    	function dynamicselect_selectval_binding(value_2, { file }) {
    		lcdata.samples[file.associd].sample = value_2;
    		$$invalidate('lcdata', lcdata);
    	}

    	const newvalue_handler = ({ file }, e) => checkNewSample(file);

    	function dynamicselect_intext_binding_1(value, { file }) {
    		lcdata.samples[file.associd].channelname = value;
    		$$invalidate('lcdata', lcdata);
    	}

    	function dynamicselect_fixedoptions_binding(value_1) {
    		lcdata.quants[lcdata.quanttype].chans = value_1;
    		$$invalidate('lcdata', lcdata);
    	}

    	function dynamicselect_fixedorder_binding(value_2) {
    		lcdata.quants[lcdata.quanttype].chanorder = value_2;
    		$$invalidate('lcdata', lcdata);
    	}

    	function dynamicselect_selectval_binding_1(value_3, { file }) {
    		lcdata.samples[file.associd].channel = value_3;
    		$$invalidate('lcdata', lcdata);
    	}

    	const selectedvalue_handler = ({ file }, e) => okChannel(file.associd);

    	const illegalvalue_handler = ({ file }, e) => badChannel(file.associd);

    	$$self.$set = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    	};

    	$$self.$capture_state = () => {
    		return { errors, lcerrors, channelError, lcdata, edited, foundNewSamples, stored, $dataset_id, $datasetFiles };
    	};

    	$$self.$inject_state = $$props => {
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    		if ('lcerrors' in $$props) $$invalidate('lcerrors', lcerrors = $$props.lcerrors);
    		if ('channelError' in $$props) channelError = $$props.channelError;
    		if ('lcdata' in $$props) $$invalidate('lcdata', lcdata = $$props.lcdata);
    		if ('edited' in $$props) $$invalidate('edited', edited = $$props.edited);
    		if ('foundNewSamples' in $$props) $$invalidate('foundNewSamples', foundNewSamples = $$props.foundNewSamples);
    		if ('stored' in $$props) $$invalidate('stored', stored = $$props.stored);
    		if ('$dataset_id' in $$props) dataset_id.set($dataset_id);
    		if ('$datasetFiles' in $$props) datasetFiles.set($datasetFiles);
    	};

    	let foundNewSamples, stored;

    	$$self.$$.update = ($$dirty = { lcdata: 1, $dataset_id: 1, edited: 1 }) => {
    		if ($$dirty.lcdata) { $$invalidate('foundNewSamples', foundNewSamples = Object.values(lcdata.samples).some(x => x.newprojsample !== '')); }
    		if ($$dirty.$dataset_id || $$dirty.edited) { $$invalidate('stored', stored = $dataset_id && !edited); }
    	};

    	return {
    		errors,
    		lcerrors,
    		lcdata,
    		edited,
    		editMade,
    		okChannel,
    		badChannel,
    		saveNewSamples,
    		checkNewSample,
    		save,
    		fetchData,
    		foundNewSamples,
    		Object,
    		stored,
    		$datasetFiles,
    		select_change_handler,
    		dynamicselect_intext_binding,
    		dynamicselect_unknowninput_binding,
    		dynamicselect_selectval_binding,
    		newvalue_handler,
    		dynamicselect_intext_binding_1,
    		dynamicselect_fixedoptions_binding,
    		dynamicselect_fixedorder_binding,
    		dynamicselect_selectval_binding_1,
    		selectedvalue_handler,
    		illegalvalue_handler
    	};
    }

    class LCheck extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$6, create_fragment$6, safe_not_equal, ["errors"]);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "LCheck", options, id: create_fragment$6.name });

    		const { ctx } = this.$$;
    		const props = options.props || {};
    		if (ctx.errors === undefined && !('errors' in props)) {
    			console_1$2.warn("<LCheck> was created without expected prop 'errors'");
    		}
    	}

    	get errors() {
    		throw new Error("<LCheck>: Props cannot be read directly from the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}

    	set errors(value) {
    		throw new Error("<LCheck>: Props cannot be set directly on the component instance unless compiling with 'accessors: true' or '<svelte:options accessors/>'");
    	}
    }

    /* src/Files.svelte generated by Svelte v3.12.1 */
    const { Object: Object_1$4 } = globals;

    const file$7 = "src/Files.svelte";

    function get_each_context$7(ctx, list, i) {
    	const child_ctx = Object_1$4.create(ctx);
    	child_ctx.fn = list[i];
    	child_ctx.each_value = list;
    	child_ctx.fn_index = i;
    	return child_ctx;
    }

    function get_each_context_1$5(ctx, list, i) {
    	const child_ctx = Object_1$4.create(ctx);
    	child_ctx.fn = list[i];
    	return child_ctx;
    }

    // (119:10) {#if fn.id in $datasetFiles}
    function create_if_block$7(ctx) {
    	var span, i;

    	const block = {
    		c: function create() {
    			span = element("span");
    			i = element("i");
    			attr_dev(i, "class", "fas fa-database");
    			add_location(i, file$7, 119, 55, 4048);
    			attr_dev(span, "class", "icon is-small has-text-primary");
    			add_location(span, file$7, 119, 10, 4003);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, i);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(span);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$7.name, type: "if", source: "(119:10) {#if fn.id in $datasetFiles}", ctx });
    	return block;
    }

    // (115:6) {#each Object.values(addedFiles).concat(files.dsfn_order.map(x => $datasetFiles[x])) as fn}
    function create_each_block_1$5(ctx) {
    	var tr, td0, span, i, t0, td1, t1, td2, t2_value = ctx.fn.name + "", t2, t3, td3, t4_value = isoTime(ctx.fn.date) + "", t4, t5, td4, t6_value = ctx.fn.size + "", t6, t7, t8, td5, t9_value = ctx.fn.instrument + "", t9, dispose;

    	function click_handler(...args) {
    		return ctx.click_handler(ctx, ...args);
    	}

    	var if_block = (ctx.fn.id in ctx.$datasetFiles) && create_if_block$7(ctx);

    	const block = {
    		c: function create() {
    			tr = element("tr");
    			td0 = element("td");
    			span = element("span");
    			i = element("i");
    			t0 = space();
    			td1 = element("td");
    			if (if_block) if_block.c();
    			t1 = space();
    			td2 = element("td");
    			t2 = text(t2_value);
    			t3 = space();
    			td3 = element("td");
    			t4 = text(t4_value);
    			t5 = space();
    			td4 = element("td");
    			t6 = text(t6_value);
    			t7 = text("MB");
    			t8 = space();
    			td5 = element("td");
    			t9 = text(t9_value);
    			attr_dev(i, "class", "fas fa-times");
    			add_location(i, file$7, 116, 90, 3900);
    			attr_dev(span, "class", "icon is-small has-text-danger");
    			add_location(span, file$7, 116, 12, 3822);
    			add_location(td0, file$7, 116, 8, 3818);
    			add_location(td1, file$7, 117, 8, 3949);
    			add_location(td2, file$7, 122, 8, 4125);
    			add_location(td3, file$7, 123, 8, 4152);
    			add_location(td4, file$7, 124, 8, 4188);
    			add_location(td5, file$7, 125, 8, 4217);
    			add_location(tr, file$7, 115, 6, 3805);
    			dispose = listen_dev(span, "click", click_handler);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tr, anchor);
    			append_dev(tr, td0);
    			append_dev(td0, span);
    			append_dev(span, i);
    			append_dev(tr, t0);
    			append_dev(tr, td1);
    			if (if_block) if_block.m(td1, null);
    			append_dev(tr, t1);
    			append_dev(tr, td2);
    			append_dev(td2, t2);
    			append_dev(tr, t3);
    			append_dev(tr, td3);
    			append_dev(td3, t4);
    			append_dev(tr, t5);
    			append_dev(tr, td4);
    			append_dev(td4, t6);
    			append_dev(td4, t7);
    			append_dev(tr, t8);
    			append_dev(tr, td5);
    			append_dev(td5, t9);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if (ctx.fn.id in ctx.$datasetFiles) {
    				if (!if_block) {
    					if_block = create_if_block$7(ctx);
    					if_block.c();
    					if_block.m(td1, null);
    				}
    			} else if (if_block) {
    				if_block.d(1);
    				if_block = null;
    			}

    			if ((changed.Object || changed.addedFiles || changed.files || changed.$datasetFiles) && t2_value !== (t2_value = ctx.fn.name + "")) {
    				set_data_dev(t2, t2_value);
    			}

    			if ((changed.Object || changed.addedFiles || changed.files || changed.$datasetFiles) && t4_value !== (t4_value = isoTime(ctx.fn.date) + "")) {
    				set_data_dev(t4, t4_value);
    			}

    			if ((changed.Object || changed.addedFiles || changed.files || changed.$datasetFiles) && t6_value !== (t6_value = ctx.fn.size + "")) {
    				set_data_dev(t6, t6_value);
    			}

    			if ((changed.Object || changed.addedFiles || changed.files || changed.$datasetFiles) && t9_value !== (t9_value = ctx.fn.instrument + "")) {
    				set_data_dev(t9, t9_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(tr);
    			}

    			if (if_block) if_block.d();
    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1$5.name, type: "each", source: "(115:6) {#each Object.values(addedFiles).concat(files.dsfn_order.map(x => $datasetFiles[x])) as fn}", ctx });
    	return block;
    }

    // (129:6) {#each Object.values(removed_files).concat(files.newfn_order.map(x => files.newFiles[x])) as fn}
    function create_each_block$7(ctx) {
    	var tr, td0, input, t0, td1, t1, td2, t2_value = ctx.fn.name + "", t2, t3, td3, t4_value = isoTime(ctx.fn.date) + "", t4, t5, td4, t6_value = ctx.fn.size + "", t6, t7, t8, td5, t9_value = ctx.fn.instrument + "", t9, t10, dispose;

    	function input_change_handler() {
    		ctx.input_change_handler.call(input, ctx);
    	}

    	const block = {
    		c: function create() {
    			tr = element("tr");
    			td0 = element("td");
    			input = element("input");
    			t0 = space();
    			td1 = element("td");
    			t1 = space();
    			td2 = element("td");
    			t2 = text(t2_value);
    			t3 = space();
    			td3 = element("td");
    			t4 = text(t4_value);
    			t5 = space();
    			td4 = element("td");
    			t6 = text(t6_value);
    			t7 = text("MB");
    			t8 = space();
    			td5 = element("td");
    			t9 = text(t9_value);
    			t10 = space();
    			attr_dev(input, "type", "checkbox");
    			add_location(input, file$7, 131, 10, 4405);
    			add_location(td0, file$7, 130, 8, 4390);
    			add_location(td1, file$7, 133, 8, 4477);
    			add_location(td2, file$7, 134, 8, 4495);
    			add_location(td3, file$7, 135, 8, 4522);
    			add_location(td4, file$7, 136, 8, 4558);
    			add_location(td5, file$7, 137, 8, 4587);
    			add_location(tr, file$7, 129, 6, 4377);
    			dispose = listen_dev(input, "change", input_change_handler);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, tr, anchor);
    			append_dev(tr, td0);
    			append_dev(td0, input);

    			input.checked = ctx.fn.checked;

    			append_dev(tr, t0);
    			append_dev(tr, td1);
    			append_dev(tr, t1);
    			append_dev(tr, td2);
    			append_dev(td2, t2);
    			append_dev(tr, t3);
    			append_dev(tr, td3);
    			append_dev(td3, t4);
    			append_dev(tr, t5);
    			append_dev(tr, td4);
    			append_dev(td4, t6);
    			append_dev(td4, t7);
    			append_dev(tr, t8);
    			append_dev(tr, td5);
    			append_dev(td5, t9);
    			append_dev(tr, t10);
    		},

    		p: function update(changed, new_ctx) {
    			ctx = new_ctx;
    			if ((changed.Object || changed.removed_files || changed.files)) input.checked = ctx.fn.checked;

    			if ((changed.Object || changed.removed_files || changed.files) && t2_value !== (t2_value = ctx.fn.name + "")) {
    				set_data_dev(t2, t2_value);
    			}

    			if ((changed.Object || changed.removed_files || changed.files) && t4_value !== (t4_value = isoTime(ctx.fn.date) + "")) {
    				set_data_dev(t4, t4_value);
    			}

    			if ((changed.Object || changed.removed_files || changed.files) && t6_value !== (t6_value = ctx.fn.size + "")) {
    				set_data_dev(t6, t6_value);
    			}

    			if ((changed.Object || changed.removed_files || changed.files) && t9_value !== (t9_value = ctx.fn.instrument + "")) {
    				set_data_dev(t9, t9_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(tr);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$7.name, type: "each", source: "(129:6) {#each Object.values(removed_files).concat(files.newfn_order.map(x => files.newFiles[x])) as fn}", ctx });
    	return block;
    }

    function create_fragment$7(ctx) {
    	var div2, input0, t0, div0, t1, t2_value = ctx.files.newfn_order.length + "", t2, t3, t4_value = ctx.selectedFiles.length + "", t4, t5, t6_value = ctx.files.dsfn_order.length + "", t6, t7, t8_value = ctx.Object.keys(ctx.removed_files).length + "", t8, t9, t10_value = ctx.Object.keys(ctx.addedFiles).length + "", t10, t11, t12, div1, button0, t13, button0_disabled_value, t14, button1, t16, button2, t17, button2_disabled_value, t18, table, thead, tr, th0, input1, t19, th1, t20, th2, t22, th3, t24, th4, t26, th5, t28, tbody, t29, dispose;

    	let each_value_1 = ctx.Object.values(ctx.addedFiles).concat(ctx.files.dsfn_order.map(ctx.func));

    	let each_blocks_1 = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks_1[i] = create_each_block_1$5(get_each_context_1$5(ctx, each_value_1, i));
    	}

    	let each_value = ctx.Object.values(ctx.removed_files).concat(ctx.files.newfn_order.map(ctx.func_1));

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$7(get_each_context$7(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			div2 = element("div");
    			input0 = element("input");
    			t0 = space();
    			div0 = element("div");
    			t1 = text("Showing ");
    			t2 = text(t2_value);
    			t3 = text(" new files (");
    			t4 = text(t4_value);
    			t5 = text(" selected), ");
    			t6 = text(t6_value);
    			t7 = text(" files in dataset (incl. ");
    			t8 = text(t8_value);
    			t9 = text(", excl. ");
    			t10 = text(t10_value);
    			t11 = text(" added files)");
    			t12 = space();
    			div1 = element("div");
    			button0 = element("button");
    			t13 = text("Save");
    			t14 = space();
    			button1 = element("button");
    			button1.textContent = "Revert";
    			t16 = space();
    			button2 = element("button");
    			t17 = text("Add selected files");
    			t18 = space();
    			table = element("table");
    			thead = element("thead");
    			tr = element("tr");
    			th0 = element("th");
    			input1 = element("input");
    			t19 = space();
    			th1 = element("th");
    			t20 = space();
    			th2 = element("th");
    			th2.textContent = "File";
    			t22 = space();
    			th3 = element("th");
    			th3.textContent = "Date";
    			t24 = space();
    			th4 = element("th");
    			th4.textContent = "Size";
    			t26 = space();
    			th5 = element("th");
    			th5.textContent = "Instrument";
    			t28 = space();
    			tbody = element("tbody");

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].c();
    			}

    			t29 = space();

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			attr_dev(input0, "class", "input is-small");
    			attr_dev(input0, "type", "text");
    			attr_dev(input0, "placeholder", "Type a query and press enter to find analyses");
    			add_location(input0, file$7, 94, 2, 2710);
    			add_location(div0, file$7, 95, 2, 2859);
    			attr_dev(button0, "class", "button is-danger is-small");
    			button0.disabled = button0_disabled_value = !ctx.changed;
    			add_location(button0, file$7, 97, 4, 3101);
    			attr_dev(button1, "class", "button is-info is-small");
    			add_location(button1, file$7, 98, 4, 3197);
    			attr_dev(button2, "class", "button is-small");
    			button2.disabled = button2_disabled_value = !ctx.selectedFiles.length;
    			add_location(button2, file$7, 99, 4, 3279);
    			add_location(div1, file$7, 96, 2, 3091);
    			attr_dev(input1, "type", "checkbox");
    			add_location(input1, file$7, 104, 12, 3461);
    			add_location(th0, file$7, 104, 8, 3457);
    			add_location(th1, file$7, 105, 8, 3552);
    			add_location(th2, file$7, 106, 8, 3570);
    			add_location(th3, file$7, 107, 8, 3592);
    			add_location(th4, file$7, 108, 8, 3614);
    			add_location(th5, file$7, 109, 8, 3636);
    			add_location(tr, file$7, 103, 6, 3444);
    			add_location(thead, file$7, 102, 4, 3430);
    			add_location(tbody, file$7, 112, 4, 3686);
    			attr_dev(table, "class", "table");
    			add_location(table, file$7, 101, 2, 3404);
    			attr_dev(div2, "class", "content is-small");
    			add_location(div2, file$7, 93, 0, 2677);

    			dispose = [
    				listen_dev(input0, "input", ctx.input0_input_handler),
    				listen_dev(input0, "keyup", ctx.findFiles),
    				listen_dev(button0, "click", ctx.save),
    				listen_dev(button1, "click", ctx.fetchFiles),
    				listen_dev(button2, "click", ctx.addFiles),
    				listen_dev(input1, "change", ctx.input1_change_handler),
    				listen_dev(input1, "click", ctx.selectAllNew)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div2, anchor);
    			append_dev(div2, input0);

    			set_input_value(input0, ctx.findQuery);

    			append_dev(div2, t0);
    			append_dev(div2, div0);
    			append_dev(div0, t1);
    			append_dev(div0, t2);
    			append_dev(div0, t3);
    			append_dev(div0, t4);
    			append_dev(div0, t5);
    			append_dev(div0, t6);
    			append_dev(div0, t7);
    			append_dev(div0, t8);
    			append_dev(div0, t9);
    			append_dev(div0, t10);
    			append_dev(div0, t11);
    			append_dev(div2, t12);
    			append_dev(div2, div1);
    			append_dev(div1, button0);
    			append_dev(button0, t13);
    			append_dev(div1, t14);
    			append_dev(div1, button1);
    			append_dev(div1, t16);
    			append_dev(div1, button2);
    			append_dev(button2, t17);
    			append_dev(div2, t18);
    			append_dev(div2, table);
    			append_dev(table, thead);
    			append_dev(thead, tr);
    			append_dev(tr, th0);
    			append_dev(th0, input1);

    			input1.checked = ctx.allNewSelector;

    			append_dev(tr, t19);
    			append_dev(tr, th1);
    			append_dev(tr, t20);
    			append_dev(tr, th2);
    			append_dev(tr, t22);
    			append_dev(tr, th3);
    			append_dev(tr, t24);
    			append_dev(tr, th4);
    			append_dev(tr, t26);
    			append_dev(tr, th5);
    			append_dev(table, t28);
    			append_dev(table, tbody);

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].m(tbody, null);
    			}

    			append_dev(tbody, t29);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(tbody, null);
    			}
    		},

    		p: function update(changed, ctx) {
    			if (changed.findQuery && (input0.value !== ctx.findQuery)) set_input_value(input0, ctx.findQuery);

    			if ((changed.files) && t2_value !== (t2_value = ctx.files.newfn_order.length + "")) {
    				set_data_dev(t2, t2_value);
    			}

    			if ((changed.selectedFiles) && t4_value !== (t4_value = ctx.selectedFiles.length + "")) {
    				set_data_dev(t4, t4_value);
    			}

    			if ((changed.files) && t6_value !== (t6_value = ctx.files.dsfn_order.length + "")) {
    				set_data_dev(t6, t6_value);
    			}

    			if ((changed.Object || changed.removed_files) && t8_value !== (t8_value = ctx.Object.keys(ctx.removed_files).length + "")) {
    				set_data_dev(t8, t8_value);
    			}

    			if ((changed.Object || changed.addedFiles) && t10_value !== (t10_value = ctx.Object.keys(ctx.addedFiles).length + "")) {
    				set_data_dev(t10, t10_value);
    			}

    			if ((changed.changed) && button0_disabled_value !== (button0_disabled_value = !ctx.changed)) {
    				prop_dev(button0, "disabled", button0_disabled_value);
    			}

    			if ((changed.selectedFiles) && button2_disabled_value !== (button2_disabled_value = !ctx.selectedFiles.length)) {
    				prop_dev(button2, "disabled", button2_disabled_value);
    			}

    			if (changed.allNewSelector) input1.checked = ctx.allNewSelector;

    			if (changed.Object || changed.addedFiles || changed.files || changed.$datasetFiles || changed.isoTime) {
    				each_value_1 = ctx.Object.values(ctx.addedFiles).concat(ctx.files.dsfn_order.map(ctx.func));

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1$5(ctx, each_value_1, i);

    					if (each_blocks_1[i]) {
    						each_blocks_1[i].p(changed, child_ctx);
    					} else {
    						each_blocks_1[i] = create_each_block_1$5(child_ctx);
    						each_blocks_1[i].c();
    						each_blocks_1[i].m(tbody, t29);
    					}
    				}

    				for (; i < each_blocks_1.length; i += 1) {
    					each_blocks_1[i].d(1);
    				}
    				each_blocks_1.length = each_value_1.length;
    			}

    			if (changed.Object || changed.removed_files || changed.files || changed.isoTime) {
    				each_value = ctx.Object.values(ctx.removed_files).concat(ctx.files.newfn_order.map(ctx.func_1));

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$7(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block$7(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(tbody, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}
    		},

    		i: noop,
    		o: noop,

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div2);
    			}

    			destroy_each(each_blocks_1, detaching);

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$7.name, type: "component", source: "", ctx });
    	return block;
    }

    let allDsSelector = false;

    function isoTime(timestamp) {
    let x = new Date(timestamp);
    return x.toISOString();
    }

    function instance$7($$self, $$props, $$invalidate) {
    	let $datasetFiles, $dataset_id;

    	validate_store(datasetFiles, 'datasetFiles');
    	component_subscribe($$self, datasetFiles, $$value => { $datasetFiles = $$value; $$invalidate('$datasetFiles', $datasetFiles); });
    	validate_store(dataset_id, 'dataset_id');
    	component_subscribe($$self, dataset_id, $$value => { $dataset_id = $$value; $$invalidate('$dataset_id', $dataset_id); });

    	

    let files = {
      newFiles: {},
      dsfn_order: [],
      newfn_order: [],
    };
    let addedFiles = {};
    let removed_files = {};
    let findQuery = '';
    let allNewSelector = false;

    async function findFiles(event) {
      if (event.keyCode === 13) {
        console.log('finding');
        const response = await getJSON(`/datasets/find/files?q=${findQuery.split(' ').join(',')}`);
        for (let [key, val] of Object.entries(response)) { $$invalidate('files', files[key] = val, files); }
      }
    }

    function selectAllNew() {
      let select_state = allNewSelector === false;
      for (let fnid in files.newFiles) {
        $$invalidate('files', files.newFiles[fnid].checked = select_state, files);
      }
    }

    function deleteFile(fnid) {
      if (fnid in $datasetFiles) {
        $$invalidate('removed_files', removed_files[fnid] = $datasetFiles[fnid], removed_files);
        $$invalidate('files', files.dsfn_order = files.dsfn_order.filter(x => x !== fnid), files);
      } else if (fnid in addedFiles) {
        $$invalidate('addedFiles', addedFiles = Object.fromEntries(Object.entries(addedFiles).filter(x => x[1].id !== fnid)));
      }
    }

    function addFiles() {
      for (let fn of Object.values(removed_files).filter(fn => fn.checked)) {
        fn.checked = false;
        //removed_files = file.removed_files.filter[fn.id] = fn;
        delete(removed_files[fn.id]);
        $$invalidate('files', files.dsfn_order = [fn.id].concat(files.dsfn_order), files);
        //files.newfn_order = files.newfn_order.filter(fnid => fnid !== fn.id);
      }
      for (let fn of Object.values(files.newFiles).filter(fn => fn.checked)) {
        fn.checked = false;
        $$invalidate('addedFiles', addedFiles[fn.id] = fn, addedFiles);
        $$invalidate('files', files.newfn_order = files.newfn_order.filter(fnid => fnid !== fn.id), files);
        //delete(files.newFiles[fn.id]);
      }
    }

    async function save() {
      let url = '/datasets/save/files/';
      let postdata = {
        dataset_id: $dataset_id,
        added_files: addedFiles,
        removed_files: removed_files,
      };
      await postJSON(url, postdata);
      fetchFiles();
    }

    async function fetchFiles() {
      let url = '/datasets/show/files/';
      url = $dataset_id ? url + $dataset_id : url;
    	const response = await getJSON(url);
      for (let [key, val] of Object.entries(response)) { $$invalidate('files', files[key] = val, files); }
      for (let key in $datasetFiles) { delete($datasetFiles[key]); }
      for (let [key, val] of Object.entries(response.datasetFiles)) { set_store_value(datasetFiles, $datasetFiles[key] = val, $datasetFiles); }
      $$invalidate('addedFiles', addedFiles = {});
      $$invalidate('removed_files', removed_files = {});
    }

    onMount(async() => {
      fetchFiles();
    });

    	function input0_input_handler() {
    		findQuery = this.value;
    		$$invalidate('findQuery', findQuery);
    	}

    	function input1_change_handler() {
    		allNewSelector = this.checked;
    		$$invalidate('allNewSelector', allNewSelector);
    	}

    	const func = (x) => $datasetFiles[x];

    	const click_handler = ({ fn }, e) => deleteFile(fn.id);

    	const func_1 = (x) => files.newFiles[x];

    	function input_change_handler({ fn, each_value, fn_index }) {
    		each_value[fn_index].checked = this.checked;
    		$$invalidate('Object', Object);
    		$$invalidate('removed_files', removed_files);
    		$$invalidate('files', files);
    	}

    	$$self.$capture_state = () => {
    		return {};
    	};

    	$$self.$inject_state = $$props => {
    		if ('files' in $$props) $$invalidate('files', files = $$props.files);
    		if ('addedFiles' in $$props) $$invalidate('addedFiles', addedFiles = $$props.addedFiles);
    		if ('removed_files' in $$props) $$invalidate('removed_files', removed_files = $$props.removed_files);
    		if ('findQuery' in $$props) $$invalidate('findQuery', findQuery = $$props.findQuery);
    		if ('allDsSelector' in $$props) allDsSelector = $$props.allDsSelector;
    		if ('allNewSelector' in $$props) $$invalidate('allNewSelector', allNewSelector = $$props.allNewSelector);
    		if ('changed' in $$props) $$invalidate('changed', changed = $$props.changed);
    		if ('selectedFiles' in $$props) $$invalidate('selectedFiles', selectedFiles = $$props.selectedFiles);
    		if ('$datasetFiles' in $$props) datasetFiles.set($datasetFiles);
    		if ('$dataset_id' in $$props) dataset_id.set($dataset_id);
    	};

    	let changed, selectedFiles;

    	$$self.$$.update = ($$dirty = { Object: 1, addedFiles: 1, removed_files: 1, files: 1 }) => {
    		if ($$dirty.Object || $$dirty.addedFiles || $$dirty.removed_files) { $$invalidate('changed', changed = Object.keys(addedFiles).length || Object.keys(removed_files).length); }
    		if ($$dirty.Object || $$dirty.files || $$dirty.removed_files) { $$invalidate('selectedFiles', selectedFiles = Object.values(files.newFiles).concat(Object.values(removed_files)).filter(fn => fn.checked)); }
    	};

    	return {
    		files,
    		addedFiles,
    		removed_files,
    		findQuery,
    		allNewSelector,
    		findFiles,
    		selectAllNew,
    		deleteFile,
    		addFiles,
    		save,
    		fetchFiles,
    		Object,
    		changed,
    		selectedFiles,
    		$datasetFiles,
    		input0_input_handler,
    		input1_change_handler,
    		func,
    		click_handler,
    		func_1,
    		input_change_handler
    	};
    }

    class Files extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$7, create_fragment$7, safe_not_equal, []);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "Files", options, id: create_fragment$7.name });
    	}
    }

    /* src/App.svelte generated by Svelte v3.12.1 */
    const { Object: Object_1$5 } = globals;

    const file$8 = "src/App.svelte";

    function get_each_context$8(ctx, list, i) {
    	const child_ctx = Object_1$5.create(ctx);
    	child_ctx.dstype = list[i];
    	return child_ctx;
    }

    function get_each_context_1$6(ctx, list, i) {
    	const child_ctx = Object_1$5.create(ctx);
    	child_ctx.expi = list[i];
    	return child_ctx;
    }

    function get_each_context_3$1(ctx, list, i) {
    	const child_ctx = Object_1$5.create(ctx);
    	child_ctx.ptype = list[i];
    	return child_ctx;
    }

    function get_each_context_2$2(ctx, list, i) {
    	const child_ctx = Object_1$5.create(ctx);
    	child_ctx.project = list[i];
    	return child_ctx;
    }

    // (237:4) {#if $dataset_id}
    function create_if_block_13(ctx) {
    	var li, a, span, li_class_value, dispose;

    	const block = {
    		c: function create() {
    			li = element("li");
    			a = element("a");
    			span = element("span");
    			span.textContent = "Files";
    			add_location(span, file$8, 238, 8, 6857);
    			add_location(a, file$8, 237, 54, 6824);
    			attr_dev(li, "class", li_class_value = ctx.tabshow === 'files' ? 'is-active': '');
    			add_location(li, file$8, 237, 4, 6774);
    			dispose = listen_dev(a, "click", ctx.showFiles);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, li, anchor);
    			append_dev(li, a);
    			append_dev(a, span);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.tabshow) && li_class_value !== (li_class_value = ctx.tabshow === 'files' ? 'is-active': '')) {
    				attr_dev(li, "class", li_class_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(li);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_13.name, type: "if", source: "(237:4) {#if $dataset_id}", ctx });
    	return block;
    }

    // (249:6) {#if dsinfo.storage_location}
    function create_if_block_12(ctx) {
    	var article, div0, t1, div1, t2_value = ctx.dsinfo.storage_location + "", t2;

    	const block = {
    		c: function create() {
    			article = element("article");
    			div0 = element("div");
    			div0.textContent = "Storage location";
    			t1 = space();
    			div1 = element("div");
    			t2 = text(t2_value);
    			attr_dev(div0, "class", "message-header");
    			add_location(div0, file$8, 250, 8, 7130);
    			attr_dev(div1, "class", "message-body");
    			add_location(div1, file$8, 251, 8, 7189);
    			attr_dev(article, "class", "message is-info");
    			add_location(article, file$8, 249, 5, 7087);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, article, anchor);
    			append_dev(article, div0);
    			append_dev(article, t1);
    			append_dev(article, div1);
    			append_dev(div1, t2);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.dsinfo) && t2_value !== (t2_value = ctx.dsinfo.storage_location + "")) {
    				set_data_dev(t2, t2_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(article);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_12.name, type: "if", source: "(249:6) {#if dsinfo.storage_location}", ctx });
    	return block;
    }

    // (257:8) {#if stored}
    function create_if_block_11$1(ctx) {
    	var i;

    	const block = {
    		c: function create() {
    			i = element("i");
    			attr_dev(i, "class", "icon fas fa-check-circle");
    			add_location(i, file$8, 257, 8, 7356);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, i, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(i);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_11$1.name, type: "if", source: "(257:8) {#if stored}", ctx });
    	return block;
    }

    // (270:12) {:else}
    function create_else_block_1$1(ctx) {
    	var t;

    	const block = {
    		c: function create() {
    			t = text("Create new project");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(t);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_else_block_1$1.name, type: "else", source: "(270:12) {:else}", ctx });
    	return block;
    }

    // (268:12) {#if isNewProject}
    function create_if_block_10$1(ctx) {
    	var t;

    	const block = {
    		c: function create() {
    			t = text("Use existing project");
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(t);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_10$1.name, type: "if", source: "(268:12) {#if isNewProject}", ctx });
    	return block;
    }

    // (285:8) {:else}
    function create_else_block$3(ctx) {
    	var input, t0, label, t2, div, select, option, dispose;

    	let each_value_3 = ctx.pdata.ptypes;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_3.length; i += 1) {
    		each_blocks[i] = create_each_block_3$1(get_each_context_3$1(ctx, each_value_3, i));
    	}

    	const block = {
    		c: function create() {
    			input = element("input");
    			t0 = space();
    			label = element("label");
    			label.textContent = "Project type";
    			t2 = space();
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			attr_dev(input, "class", "input");
    			attr_dev(input, "type", "text");
    			attr_dev(input, "placeholder", "Project name");
    			add_location(input, file$8, 285, 8, 8464);
    			attr_dev(label, "class", "label");
    			add_location(label, file$8, 286, 8, 8589);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$8, 289, 12, 8720);
    			if (ctx.dsinfo.ptype_id === void 0) add_render_callback(() => ctx.select_change_handler_1.call(select));
    			add_location(select, file$8, 288, 10, 8670);
    			attr_dev(div, "class", "select");
    			add_location(div, file$8, 287, 8, 8639);

    			dispose = [
    				listen_dev(input, "input", ctx.input_input_handler),
    				listen_dev(input, "change", ctx.editMade),
    				listen_dev(select, "change", ctx.select_change_handler_1)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, input, anchor);

    			set_input_value(input, ctx.dsinfo.newprojectname);

    			insert_dev(target, t0, anchor);
    			insert_dev(target, label, anchor);
    			insert_dev(target, t2, anchor);
    			insert_dev(target, div, anchor);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.ptype_id);
    		},

    		p: function update(changed, ctx) {
    			if (changed.dsinfo && (input.value !== ctx.dsinfo.newprojectname)) set_input_value(input, ctx.dsinfo.newprojectname);

    			if (changed.pdata) {
    				each_value_3 = ctx.pdata.ptypes;

    				let i;
    				for (i = 0; i < each_value_3.length; i += 1) {
    					const child_ctx = get_each_context_3$1(ctx, each_value_3, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_3$1(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_3.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.ptype_id);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(input);
    				detach_dev(t0);
    				detach_dev(label);
    				detach_dev(t2);
    				detach_dev(div);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_else_block$3.name, type: "else", source: "(285:8) {:else}", ctx });
    	return block;
    }

    // (276:8) {#if !isNewProject}
    function create_if_block_9$1(ctx) {
    	var div, select, option, dispose;

    	let each_value_2 = ctx.pdata.projects;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_2.length; i += 1) {
    		each_blocks[i] = create_each_block_2$2(get_each_context_2$2(ctx, each_value_2, i));
    	}

    	const block = {
    		c: function create() {
    			div = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$8, 278, 14, 8213);
    			if (ctx.dsinfo.project_id === void 0) add_render_callback(() => ctx.select_change_handler.call(select));
    			add_location(select, file$8, 277, 12, 8130);
    			attr_dev(div, "class", "select");
    			add_location(div, file$8, 276, 10, 8097);

    			dispose = [
    				listen_dev(select, "change", ctx.select_change_handler),
    				listen_dev(select, "change", ctx.project_selected)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.project_id);
    		},

    		p: function update(changed, ctx) {
    			if (changed.pdata) {
    				each_value_2 = ctx.pdata.projects;

    				let i;
    				for (i = 0; i < each_value_2.length; i += 1) {
    					const child_ctx = get_each_context_2$2(ctx, each_value_2, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_2$2(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_2.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.project_id);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_9$1.name, type: "if", source: "(276:8) {#if !isNewProject}", ctx });
    	return block;
    }

    // (291:12) {#each pdata.ptypes as ptype}
    function create_each_block_3$1(ctx) {
    	var option, t_value = ctx.ptype.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.ptype.id;
    			option.value = option.__value;
    			add_location(option, file$8, 291, 12, 8827);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.pdata) && t_value !== (t_value = ctx.ptype.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.pdata) && option_value_value !== (option_value_value = ctx.ptype.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_3$1.name, type: "each", source: "(291:12) {#each pdata.ptypes as ptype}", ctx });
    	return block;
    }

    // (280:14) {#each pdata.projects as project}
    function create_each_block_2$2(ctx) {
    	var option, t_value = ctx.project.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.project.id;
    			option.value = option.__value;
    			add_location(option, file$8, 280, 14, 8328);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.pdata) && t_value !== (t_value = ctx.project.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.pdata) && option_value_value !== (option_value_value = ctx.project.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_2$2.name, type: "each", source: "(280:14) {#each pdata.projects as project}", ctx });
    	return block;
    }

    // (297:8) {#if isExternal}
    function create_if_block_8$1(ctx) {
    	var span, t0, t1_value = ctx.dsinfo.pi.name + "", t1;

    	const block = {
    		c: function create() {
    			span = element("span");
    			t0 = text("External project: ");
    			t1 = text(t1_value);
    			attr_dev(span, "class", "tag is-success is-medium");
    			add_location(span, file$8, 297, 8, 8976);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, t0);
    			append_dev(span, t1);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.dsinfo) && t1_value !== (t1_value = ctx.dsinfo.pi.name + "")) {
    				set_data_dev(t1, t1_value);
    			}
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(span);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_8$1.name, type: "if", source: "(297:8) {#if isExternal}", ctx });
    	return block;
    }

    // (303:6) {#if isExternal}
    function create_if_block_3$4(ctx) {
    	var div1, label, t0, t1, t2, div0, input, dispose;

    	function select_block_type_2(changed, ctx) {
    		if (ctx.isNewProject && ctx.isNewPI) return create_if_block_6$2;
    		if (ctx.isNewProject) return create_if_block_7$1;
    	}

    	var current_block_type = select_block_type_2(null, ctx);
    	var if_block0 = current_block_type && current_block_type(ctx);

    	function select_block_type_3(changed, ctx) {
    		if (ctx.isNewProject && !ctx.isNewPI) return create_if_block_4$3;
    		if (ctx.isNewProject) return create_if_block_5$2;
    	}

    	var current_block_type_1 = select_block_type_3(null, ctx);
    	var if_block1 = current_block_type_1 && current_block_type_1(ctx);

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			label = element("label");
    			t0 = text("contact(s)\n          ");
    			if (if_block0) if_block0.c();
    			t1 = space();
    			if (if_block1) if_block1.c();
    			t2 = space();
    			div0 = element("div");
    			input = element("input");
    			attr_dev(label, "class", "label");
    			add_location(label, file$8, 304, 8, 9157);
    			attr_dev(input, "class", "input");
    			attr_dev(input, "type", "text");
    			attr_dev(input, "placeholder", "operational contact email (e.g. postdoc)");
    			add_location(input, file$8, 328, 10, 10164);
    			attr_dev(div0, "class", "control");
    			add_location(div0, file$8, 327, 8, 10132);
    			attr_dev(div1, "class", "field");
    			add_location(div1, file$8, 303, 6, 9129);

    			dispose = [
    				listen_dev(input, "input", ctx.input_input_handler_2),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, label);
    			append_dev(label, t0);
    			if (if_block0) if_block0.m(label, null);
    			append_dev(div1, t1);
    			if (if_block1) if_block1.m(div1, null);
    			append_dev(div1, t2);
    			append_dev(div1, div0);
    			append_dev(div0, input);

    			set_input_value(input, ctx.dsinfo.externalcontactmail);
    		},

    		p: function update(changed, ctx) {
    			if (current_block_type !== (current_block_type = select_block_type_2(changed, ctx))) {
    				if (if_block0) if_block0.d(1);
    				if_block0 = current_block_type && current_block_type(ctx);
    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(label, null);
    				}
    			}

    			if (current_block_type_1 === (current_block_type_1 = select_block_type_3(changed, ctx)) && if_block1) {
    				if_block1.p(changed, ctx);
    			} else {
    				if (if_block1) if_block1.d(1);
    				if_block1 = current_block_type_1 && current_block_type_1(ctx);
    				if (if_block1) {
    					if_block1.c();
    					if_block1.m(div1, t2);
    				}
    			}

    			if (changed.dsinfo && (input.value !== ctx.dsinfo.externalcontactmail)) set_input_value(input, ctx.dsinfo.externalcontactmail);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			if (if_block0) if_block0.d();
    			if (if_block1) if_block1.d();
    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_3$4.name, type: "if", source: "(303:6) {#if isExternal}", ctx });
    	return block;
    }

    // (308:33) 
    function create_if_block_7$1(ctx) {
    	var a, dispose;

    	const block = {
    		c: function create() {
    			a = element("a");
    			a.textContent = "Create new PI";
    			attr_dev(a, "class", "button is-danger is-outlined is-small");
    			add_location(a, file$8, 308, 10, 9387);
    			dispose = listen_dev(a, "click", ctx.click_handler_1);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, a, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(a);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_7$1.name, type: "if", source: "(308:33) ", ctx });
    	return block;
    }

    // (306:10) {#if isNewProject && isNewPI}
    function create_if_block_6$2(ctx) {
    	var a, dispose;

    	const block = {
    		c: function create() {
    			a = element("a");
    			a.textContent = "Use existing PI";
    			attr_dev(a, "class", "button is-danger is-outlined is-small");
    			add_location(a, file$8, 306, 10, 9239);
    			dispose = listen_dev(a, "click", ctx.click_handler);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, a, anchor);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(a);
    			}

    			dispose();
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_6$2.name, type: "if", source: "(306:10) {#if isNewProject && isNewPI}", ctx });
    	return block;
    }

    // (323:31) 
    function create_if_block_5$2(ctx) {
    	var div, input, dispose;

    	const block = {
    		c: function create() {
    			div = element("div");
    			input = element("input");
    			attr_dev(input, "class", "input");
    			attr_dev(input, "type", "text");
    			attr_dev(input, "placeholder", "PI name");
    			add_location(input, file$8, 324, 10, 9989);
    			attr_dev(div, "class", "control");
    			add_location(div, file$8, 323, 8, 9957);

    			dispose = [
    				listen_dev(input, "input", ctx.input_input_handler_1),
    				listen_dev(input, "input", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, input);

    			set_input_value(input, ctx.dsinfo.newpiname);
    		},

    		p: function update(changed, ctx) {
    			if (changed.dsinfo && (input.value !== ctx.dsinfo.newpiname)) set_input_value(input, ctx.dsinfo.newpiname);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div);
    			}

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_5$2.name, type: "if", source: "(323:31) ", ctx });
    	return block;
    }

    // (312:8) {#if isNewProject && !isNewPI}
    function create_if_block_4$3(ctx) {
    	var div1, div0, select, option, dispose;

    	let each_value_1 = ctx.pdata.external_pis;

    	let each_blocks = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks[i] = create_each_block_1$6(get_each_context_1$6(ctx, each_value_1, i));
    	}

    	const block = {
    		c: function create() {
    			div1 = element("div");
    			div0 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$8, 315, 8, 9695);
    			if (ctx.dsinfo.pi === void 0) add_render_callback(() => ctx.select_change_handler_2.call(select));
    			add_location(select, file$8, 314, 12, 9634);
    			attr_dev(div0, "class", "select");
    			add_location(div0, file$8, 313, 10, 9601);
    			attr_dev(div1, "class", "control");
    			add_location(div1, file$8, 312, 8, 9569);

    			dispose = [
    				listen_dev(select, "change", ctx.select_change_handler_2),
    				listen_dev(select, "change", ctx.editMade)
    			];
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, div1, anchor);
    			append_dev(div1, div0);
    			append_dev(div0, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.pi);
    		},

    		p: function update(changed, ctx) {
    			if (changed.pdata) {
    				each_value_1 = ctx.pdata.external_pis;

    				let i;
    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1$6(ctx, each_value_1, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block_1$6(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value_1.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.pi);
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(div1);
    			}

    			destroy_each(each_blocks, detaching);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_4$3.name, type: "if", source: "(312:8) {#if isNewProject && !isNewPI}", ctx });
    	return block;
    }

    // (317:14) {#each pdata.external_pis as expi}
    function create_each_block_1$6(ctx) {
    	var option, t_value = ctx.expi.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.expi;
    			option.value = option.__value;
    			add_location(option, file$8, 317, 14, 9811);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.pdata) && t_value !== (t_value = ctx.expi.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.pdata) && option_value_value !== (option_value_value = ctx.expi)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block_1$6.name, type: "each", source: "(317:14) {#each pdata.external_pis as expi}", ctx });
    	return block;
    }

    // (340:14) {#each pdata.datasettypes as dstype}
    function create_each_block$8(ctx) {
    	var option, t_value = ctx.dstype.name + "", t, option_value_value;

    	const block = {
    		c: function create() {
    			option = element("option");
    			t = text(t_value);
    			option.__value = option_value_value = ctx.dstype.id;
    			option.value = option.__value;
    			add_location(option, file$8, 340, 14, 10707);
    		},

    		m: function mount(target, anchor) {
    			insert_dev(target, option, anchor);
    			append_dev(option, t);
    		},

    		p: function update(changed, ctx) {
    			if ((changed.pdata) && t_value !== (t_value = ctx.dstype.name + "")) {
    				set_data_dev(t, t_value);
    			}

    			if ((changed.pdata) && option_value_value !== (option_value_value = ctx.dstype.id)) {
    				prop_dev(option, "__value", option_value_value);
    			}

    			option.value = option.__value;
    		},

    		d: function destroy(detaching) {
    			if (detaching) {
    				detach_dev(option);
    			}
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_each_block$8.name, type: "each", source: "(340:14) {#each pdata.datasettypes as dstype}", ctx });
    	return block;
    }

    // (355:6) {#if showMsdata}
    function create_if_block_2$5(ctx) {
    	var updating_dsinfo, updating_isNewExperiment, t, updating_errors, current;

    	function msdata_dsinfo_binding(value) {
    		ctx.msdata_dsinfo_binding.call(null, value);
    		updating_dsinfo = true;
    		add_flush_callback(() => updating_dsinfo = false);
    	}

    	function msdata_isNewExperiment_binding(value_1) {
    		ctx.msdata_isNewExperiment_binding.call(null, value_1);
    		updating_isNewExperiment = true;
    		add_flush_callback(() => updating_isNewExperiment = false);
    	}

    	let msdata_props = {
    		experiments: ctx.experiments,
    		prefracs: ctx.pdata.prefracs,
    		hirief_ranges: ctx.pdata.hirief_ranges
    	};
    	if (ctx.dsinfo !== void 0) {
    		msdata_props.dsinfo = ctx.dsinfo;
    	}
    	if (ctx.isNewExperiment !== void 0) {
    		msdata_props.isNewExperiment = ctx.isNewExperiment;
    	}
    	var msdata = new Msdata({ props: msdata_props, $$inline: true });

    	ctx.msdata_binding(msdata);
    	binding_callbacks.push(() => bind(msdata, 'dsinfo', msdata_dsinfo_binding));
    	binding_callbacks.push(() => bind(msdata, 'isNewExperiment', msdata_isNewExperiment_binding));
    	msdata.$on("edited", ctx.editMade);

    	function acquicomp_1_errors_binding(value_2) {
    		ctx.acquicomp_1_errors_binding.call(null, value_2);
    		updating_errors = true;
    		add_flush_callback(() => updating_errors = false);
    	}

    	let acquicomp_1_props = {};
    	if (ctx.errors.acqui !== void 0) {
    		acquicomp_1_props.errors = ctx.errors.acqui;
    	}
    	var acquicomp_1 = new Acquicomp({ props: acquicomp_1_props, $$inline: true });

    	ctx.acquicomp_1_binding(acquicomp_1);
    	binding_callbacks.push(() => bind(acquicomp_1, 'errors', acquicomp_1_errors_binding));

    	const block = {
    		c: function create() {
    			msdata.$$.fragment.c();
    			t = space();
    			acquicomp_1.$$.fragment.c();
    		},

    		m: function mount(target, anchor) {
    			mount_component(msdata, target, anchor);
    			insert_dev(target, t, anchor);
    			mount_component(acquicomp_1, target, anchor);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			var msdata_changes = {};
    			if (changed.experiments) msdata_changes.experiments = ctx.experiments;
    			if (changed.pdata) msdata_changes.prefracs = ctx.pdata.prefracs;
    			if (changed.pdata) msdata_changes.hirief_ranges = ctx.pdata.hirief_ranges;
    			if (!updating_dsinfo && changed.dsinfo) {
    				msdata_changes.dsinfo = ctx.dsinfo;
    			}
    			if (!updating_isNewExperiment && changed.isNewExperiment) {
    				msdata_changes.isNewExperiment = ctx.isNewExperiment;
    			}
    			msdata.$set(msdata_changes);

    			var acquicomp_1_changes = {};
    			if (!updating_errors && changed.errors) {
    				acquicomp_1_changes.errors = ctx.errors.acqui;
    			}
    			acquicomp_1.$set(acquicomp_1_changes);
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(msdata.$$.fragment, local);

    			transition_in(acquicomp_1.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(msdata.$$.fragment, local);
    			transition_out(acquicomp_1.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			ctx.msdata_binding(null);

    			destroy_component(msdata, detaching);

    			if (detaching) {
    				detach_dev(t);
    			}

    			ctx.acquicomp_1_binding(null);

    			destroy_component(acquicomp_1, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_2$5.name, type: "if", source: "(355:6) {#if showMsdata}", ctx });
    	return block;
    }

    // (359:6) {#if (components.indexOf('sampleprep')> -1)}
    function create_if_block_1$6(ctx) {
    	var updating_errors, current;

    	function prepcomp_1_errors_binding(value) {
    		ctx.prepcomp_1_errors_binding.call(null, value);
    		updating_errors = true;
    		add_flush_callback(() => updating_errors = false);
    	}

    	let prepcomp_1_props = {};
    	if (ctx.errors.sprep !== void 0) {
    		prepcomp_1_props.errors = ctx.errors.sprep;
    	}
    	var prepcomp_1 = new Prepcomp({ props: prepcomp_1_props, $$inline: true });

    	ctx.prepcomp_1_binding(prepcomp_1);
    	binding_callbacks.push(() => bind(prepcomp_1, 'errors', prepcomp_1_errors_binding));

    	const block = {
    		c: function create() {
    			prepcomp_1.$$.fragment.c();
    		},

    		m: function mount(target, anchor) {
    			mount_component(prepcomp_1, target, anchor);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			var prepcomp_1_changes = {};
    			if (!updating_errors && changed.errors) {
    				prepcomp_1_changes.errors = ctx.errors.sprep;
    			}
    			prepcomp_1.$set(prepcomp_1_changes);
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(prepcomp_1.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(prepcomp_1.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			ctx.prepcomp_1_binding(null);

    			destroy_component(prepcomp_1, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block_1$6.name, type: "if", source: "(359:6) {#if (components.indexOf('sampleprep')> -1)}", ctx });
    	return block;
    }

    // (362:6) {#if (Object.keys($datasetFiles).length && components.indexOf('labelchecksamples')>-1)}
    function create_if_block$8(ctx) {
    	var updating_errors, current;

    	function lcheck_errors_binding(value) {
    		ctx.lcheck_errors_binding.call(null, value);
    		updating_errors = true;
    		add_flush_callback(() => updating_errors = false);
    	}

    	let lcheck_props = {};
    	if (ctx.errors.lc !== void 0) {
    		lcheck_props.errors = ctx.errors.lc;
    	}
    	var lcheck = new LCheck({ props: lcheck_props, $$inline: true });

    	ctx.lcheck_binding(lcheck);
    	binding_callbacks.push(() => bind(lcheck, 'errors', lcheck_errors_binding));

    	const block = {
    		c: function create() {
    			lcheck.$$.fragment.c();
    		},

    		m: function mount(target, anchor) {
    			mount_component(lcheck, target, anchor);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			var lcheck_changes = {};
    			if (!updating_errors && changed.errors) {
    				lcheck_changes.errors = ctx.errors.lc;
    			}
    			lcheck.$set(lcheck_changes);
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(lcheck.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(lcheck.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			ctx.lcheck_binding(null);

    			destroy_component(lcheck, detaching);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_if_block$8.name, type: "if", source: "(362:6) {#if (Object.keys($datasetFiles).length && components.indexOf('labelchecksamples')>-1)}", ctx });
    	return block;
    }

    function create_fragment$8(ctx) {
    	var t0, div0, ul, li, a0, span, li_class_value, t2, t3, h4, t5, div9, div8, t6, h5, t7, button0, t8, button0_disabled_value, t9, button1, t10, button1_disabled_value, t11, div2, label0, t12, a1, t13, div1, t14, t15, t16, div5, label1, t18, div4, div3, select, option, t20, div7, label2, t22, div6, input, t23, t24, show_if_1 = (ctx.components.indexOf('sampleprep')> -1), t25, show_if = (ctx.Object.keys(ctx.$datasetFiles).length && ctx.components.indexOf('labelchecksamples')>-1), t26, div10, current, dispose;

    	var errornotif = new ErrorNotif({
    		props: {
    		cssclass: "sticky",
    		errors: ctx.Object.values(ctx.saveerrors).flat().concat(ctx.Object.values(ctx.errors).flat())
    	},
    		$$inline: true
    	});

    	var if_block0 = (ctx.$dataset_id) && create_if_block_13(ctx);

    	var if_block1 = (ctx.dsinfo.storage_location) && create_if_block_12(ctx);

    	var if_block2 = (stored) && create_if_block_11$1(ctx);

    	function select_block_type(changed, ctx) {
    		if (ctx.isNewProject) return create_if_block_10$1;
    		return create_else_block_1$1;
    	}

    	var current_block_type = select_block_type(null, ctx);
    	var if_block3 = current_block_type(ctx);

    	function select_block_type_1(changed, ctx) {
    		if (!ctx.isNewProject) return create_if_block_9$1;
    		return create_else_block$3;
    	}

    	var current_block_type_1 = select_block_type_1(null, ctx);
    	var if_block4 = current_block_type_1(ctx);

    	var if_block5 = (ctx.isExternal) && create_if_block_8$1(ctx);

    	var if_block6 = (ctx.isExternal) && create_if_block_3$4(ctx);

    	let each_value = ctx.pdata.datasettypes;

    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block$8(get_each_context$8(ctx, each_value, i));
    	}

    	var if_block7 = (ctx.showMsdata) && create_if_block_2$5(ctx);

    	var if_block8 = (show_if_1) && create_if_block_1$6(ctx);

    	var if_block9 = (show_if) && create_if_block$8(ctx);

    	let files_props = {};
    	var files = new Files({ props: files_props, $$inline: true });

    	ctx.files_binding(files);

    	const block = {
    		c: function create() {
    			errornotif.$$.fragment.c();
    			t0 = space();
    			div0 = element("div");
    			ul = element("ul");
    			li = element("li");
    			a0 = element("a");
    			span = element("span");
    			span.textContent = "Metadata";
    			t2 = space();
    			if (if_block0) if_block0.c();
    			t3 = space();
    			h4 = element("h4");
    			h4.textContent = "Dataset";
    			t5 = space();
    			div9 = element("div");
    			div8 = element("div");
    			if (if_block1) if_block1.c();
    			t6 = space();
    			h5 = element("h5");
    			if (if_block2) if_block2.c();
    			t7 = text("\n        Basics\n        ");
    			button0 = element("button");
    			t8 = text("Save");
    			t9 = space();
    			button1 = element("button");
    			t10 = text("Revert");
    			t11 = space();
    			div2 = element("div");
    			label0 = element("label");
    			t12 = text("Project\n          ");
    			a1 = element("a");
    			if_block3.c();
    			t13 = space();
    			div1 = element("div");
    			if_block4.c();
    			t14 = space();
    			if (if_block5) if_block5.c();
    			t15 = space();
    			if (if_block6) if_block6.c();
    			t16 = space();
    			div5 = element("div");
    			label1 = element("label");
    			label1.textContent = "Dataset type";
    			t18 = space();
    			div4 = element("div");
    			div3 = element("div");
    			select = element("select");
    			option = element("option");
    			option.textContent = "Please select one";

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t20 = space();
    			div7 = element("div");
    			label2 = element("label");
    			label2.textContent = "Run name";
    			t22 = space();
    			div6 = element("div");
    			input = element("input");
    			t23 = space();
    			if (if_block7) if_block7.c();
    			t24 = space();
    			if (if_block8) if_block8.c();
    			t25 = space();
    			if (if_block9) if_block9.c();
    			t26 = space();
    			div10 = element("div");
    			files.$$.fragment.c();
    			add_location(span, file$8, 234, 8, 6716);
    			add_location(a0, file$8, 233, 53, 6680);
    			attr_dev(li, "class", li_class_value = ctx.tabshow === 'meta' ? 'is-active': '');
    			add_location(li, file$8, 233, 4, 6631);
    			add_location(ul, file$8, 232, 1, 6622);
    			attr_dev(div0, "class", "tabs is-toggle is-centered is-small");
    			add_location(div0, file$8, 231, 0, 6571);
    			attr_dev(h4, "class", "title is-4");
    			add_location(h4, file$8, 244, 0, 6911);
    			attr_dev(button0, "class", "button is-small is-danger has-text-weight-bold");
    			button0.disabled = button0_disabled_value = !ctx.edited;
    			add_location(button0, file$8, 260, 8, 7434);
    			attr_dev(button1, "class", "button is-small is-info has-text-weight-bold");
    			button1.disabled = button1_disabled_value = !ctx.edited || !ctx.dsinfo.datatype_id;
    			add_location(button1, file$8, 261, 8, 7554);
    			attr_dev(h5, "class", "has-text-primary title is-5");
    			add_location(h5, file$8, 255, 6, 7286);
    			attr_dev(a1, "class", "button is-danger is-outlined is-small");
    			add_location(a1, file$8, 266, 10, 7788);
    			attr_dev(label0, "class", "label");
    			add_location(label0, file$8, 265, 8, 7749);
    			attr_dev(div1, "class", "control");
    			add_location(div1, file$8, 274, 8, 8037);
    			attr_dev(div2, "class", "field");
    			add_location(div2, file$8, 264, 6, 7720);
    			attr_dev(label1, "class", "label");
    			add_location(label1, file$8, 334, 8, 10393);
    			option.disabled = true;
    			option.__value = "";
    			option.value = option.__value;
    			add_location(option, file$8, 338, 14, 10589);
    			if (ctx.dsinfo.datatype_id === void 0) add_render_callback(() => ctx.select_change_handler_3.call(select));
    			add_location(select, file$8, 337, 12, 10508);
    			attr_dev(div3, "class", "select");
    			add_location(div3, file$8, 336, 10, 10475);
    			attr_dev(div4, "class", "control");
    			add_location(div4, file$8, 335, 8, 10443);
    			attr_dev(div5, "class", "field");
    			add_location(div5, file$8, 333, 6, 10365);
    			attr_dev(label2, "class", "label");
    			add_location(label2, file$8, 348, 8, 10880);
    			attr_dev(input, "class", "input");
    			attr_dev(input, "type", "text");
    			attr_dev(input, "placeholder", "E.g set1, lc3, rerun5b, etc");
    			add_location(input, file$8, 350, 10, 10958);
    			attr_dev(div6, "class", "control");
    			add_location(div6, file$8, 349, 8, 10926);
    			attr_dev(div7, "class", "field");
    			add_location(div7, file$8, 347, 6, 10852);
    			attr_dev(div8, "class", "box");
    			attr_dev(div8, "id", "project");
    			add_location(div8, file$8, 246, 4, 7010);
    			set_style(div9, "display", (ctx.tabshow !== 'meta' ? 'none' : ''));
    			add_location(div9, file$8, 245, 0, 6948);
    			set_style(div10, "display", (ctx.tabshow !== 'files' ? 'none' : ''));
    			add_location(div10, file$8, 367, 0, 11739);

    			dispose = [
    				listen_dev(a0, "click", ctx.showMetadata),
    				listen_dev(button0, "click", ctx.save),
    				listen_dev(button1, "click", ctx.fetchDataset),
    				listen_dev(a1, "click", ctx.toggle_project),
    				listen_dev(select, "change", ctx.select_change_handler_3),
    				listen_dev(select, "change", ctx.getcomponents),
    				listen_dev(input, "input", ctx.input_input_handler_3),
    				listen_dev(input, "change", ctx.editMade)
    			];
    		},

    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},

    		m: function mount(target, anchor) {
    			mount_component(errornotif, target, anchor);
    			insert_dev(target, t0, anchor);
    			insert_dev(target, div0, anchor);
    			append_dev(div0, ul);
    			append_dev(ul, li);
    			append_dev(li, a0);
    			append_dev(a0, span);
    			append_dev(ul, t2);
    			if (if_block0) if_block0.m(ul, null);
    			insert_dev(target, t3, anchor);
    			insert_dev(target, h4, anchor);
    			insert_dev(target, t5, anchor);
    			insert_dev(target, div9, anchor);
    			append_dev(div9, div8);
    			if (if_block1) if_block1.m(div8, null);
    			append_dev(div8, t6);
    			append_dev(div8, h5);
    			if (if_block2) if_block2.m(h5, null);
    			append_dev(h5, t7);
    			append_dev(h5, button0);
    			append_dev(button0, t8);
    			append_dev(h5, t9);
    			append_dev(h5, button1);
    			append_dev(button1, t10);
    			append_dev(div8, t11);
    			append_dev(div8, div2);
    			append_dev(div2, label0);
    			append_dev(label0, t12);
    			append_dev(label0, a1);
    			if_block3.m(a1, null);
    			append_dev(div2, t13);
    			append_dev(div2, div1);
    			if_block4.m(div1, null);
    			append_dev(div1, t14);
    			if (if_block5) if_block5.m(div1, null);
    			append_dev(div8, t15);
    			if (if_block6) if_block6.m(div8, null);
    			append_dev(div8, t16);
    			append_dev(div8, div5);
    			append_dev(div5, label1);
    			append_dev(div5, t18);
    			append_dev(div5, div4);
    			append_dev(div4, div3);
    			append_dev(div3, select);
    			append_dev(select, option);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].m(select, null);
    			}

    			select_option(select, ctx.dsinfo.datatype_id);

    			append_dev(div8, t20);
    			append_dev(div8, div7);
    			append_dev(div7, label2);
    			append_dev(div7, t22);
    			append_dev(div7, div6);
    			append_dev(div6, input);

    			set_input_value(input, ctx.dsinfo.runname);

    			append_dev(div8, t23);
    			if (if_block7) if_block7.m(div8, null);
    			append_dev(div8, t24);
    			if (if_block8) if_block8.m(div8, null);
    			append_dev(div8, t25);
    			if (if_block9) if_block9.m(div8, null);
    			insert_dev(target, t26, anchor);
    			insert_dev(target, div10, anchor);
    			mount_component(files, div10, null);
    			current = true;
    		},

    		p: function update(changed, ctx) {
    			var errornotif_changes = {};
    			if (changed.saveerrors || changed.errors) errornotif_changes.errors = ctx.Object.values(ctx.saveerrors).flat().concat(ctx.Object.values(ctx.errors).flat());
    			errornotif.$set(errornotif_changes);

    			if ((!current || changed.tabshow) && li_class_value !== (li_class_value = ctx.tabshow === 'meta' ? 'is-active': '')) {
    				attr_dev(li, "class", li_class_value);
    			}

    			if (ctx.$dataset_id) {
    				if (if_block0) {
    					if_block0.p(changed, ctx);
    				} else {
    					if_block0 = create_if_block_13(ctx);
    					if_block0.c();
    					if_block0.m(ul, null);
    				}
    			} else if (if_block0) {
    				if_block0.d(1);
    				if_block0 = null;
    			}

    			if (ctx.dsinfo.storage_location) {
    				if (if_block1) {
    					if_block1.p(changed, ctx);
    				} else {
    					if_block1 = create_if_block_12(ctx);
    					if_block1.c();
    					if_block1.m(div8, t6);
    				}
    			} else if (if_block1) {
    				if_block1.d(1);
    				if_block1 = null;
    			}

    			if ((!current || changed.edited) && button0_disabled_value !== (button0_disabled_value = !ctx.edited)) {
    				prop_dev(button0, "disabled", button0_disabled_value);
    			}

    			if ((!current || changed.edited || changed.dsinfo) && button1_disabled_value !== (button1_disabled_value = !ctx.edited || !ctx.dsinfo.datatype_id)) {
    				prop_dev(button1, "disabled", button1_disabled_value);
    			}

    			if (current_block_type !== (current_block_type = select_block_type(changed, ctx))) {
    				if_block3.d(1);
    				if_block3 = current_block_type(ctx);
    				if (if_block3) {
    					if_block3.c();
    					if_block3.m(a1, null);
    				}
    			}

    			if (current_block_type_1 === (current_block_type_1 = select_block_type_1(changed, ctx)) && if_block4) {
    				if_block4.p(changed, ctx);
    			} else {
    				if_block4.d(1);
    				if_block4 = current_block_type_1(ctx);
    				if (if_block4) {
    					if_block4.c();
    					if_block4.m(div1, t14);
    				}
    			}

    			if (ctx.isExternal) {
    				if (if_block5) {
    					if_block5.p(changed, ctx);
    				} else {
    					if_block5 = create_if_block_8$1(ctx);
    					if_block5.c();
    					if_block5.m(div1, null);
    				}
    			} else if (if_block5) {
    				if_block5.d(1);
    				if_block5 = null;
    			}

    			if (ctx.isExternal) {
    				if (if_block6) {
    					if_block6.p(changed, ctx);
    				} else {
    					if_block6 = create_if_block_3$4(ctx);
    					if_block6.c();
    					if_block6.m(div8, t16);
    				}
    			} else if (if_block6) {
    				if_block6.d(1);
    				if_block6 = null;
    			}

    			if (changed.pdata) {
    				each_value = ctx.pdata.datasettypes;

    				let i;
    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context$8(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(changed, child_ctx);
    					} else {
    						each_blocks[i] = create_each_block$8(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(select, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}
    				each_blocks.length = each_value.length;
    			}

    			if (changed.dsinfo) select_option(select, ctx.dsinfo.datatype_id);
    			if (changed.dsinfo && (input.value !== ctx.dsinfo.runname)) set_input_value(input, ctx.dsinfo.runname);

    			if (ctx.showMsdata) {
    				if (if_block7) {
    					if_block7.p(changed, ctx);
    					transition_in(if_block7, 1);
    				} else {
    					if_block7 = create_if_block_2$5(ctx);
    					if_block7.c();
    					transition_in(if_block7, 1);
    					if_block7.m(div8, t24);
    				}
    			} else if (if_block7) {
    				group_outros();
    				transition_out(if_block7, 1, 1, () => {
    					if_block7 = null;
    				});
    				check_outros();
    			}

    			if (changed.components) show_if_1 = (ctx.components.indexOf('sampleprep')> -1);

    			if (show_if_1) {
    				if (if_block8) {
    					if_block8.p(changed, ctx);
    					transition_in(if_block8, 1);
    				} else {
    					if_block8 = create_if_block_1$6(ctx);
    					if_block8.c();
    					transition_in(if_block8, 1);
    					if_block8.m(div8, t25);
    				}
    			} else if (if_block8) {
    				group_outros();
    				transition_out(if_block8, 1, 1, () => {
    					if_block8 = null;
    				});
    				check_outros();
    			}

    			if (changed.$datasetFiles || changed.components) show_if = (ctx.Object.keys(ctx.$datasetFiles).length && ctx.components.indexOf('labelchecksamples')>-1);

    			if (show_if) {
    				if (if_block9) {
    					if_block9.p(changed, ctx);
    					transition_in(if_block9, 1);
    				} else {
    					if_block9 = create_if_block$8(ctx);
    					if_block9.c();
    					transition_in(if_block9, 1);
    					if_block9.m(div8, null);
    				}
    			} else if (if_block9) {
    				group_outros();
    				transition_out(if_block9, 1, 1, () => {
    					if_block9 = null;
    				});
    				check_outros();
    			}

    			if (!current || changed.tabshow) {
    				set_style(div9, "display", (ctx.tabshow !== 'meta' ? 'none' : ''));
    			}

    			var files_changes = {};
    			files.$set(files_changes);

    			if (!current || changed.tabshow) {
    				set_style(div10, "display", (ctx.tabshow !== 'files' ? 'none' : ''));
    			}
    		},

    		i: function intro(local) {
    			if (current) return;
    			transition_in(errornotif.$$.fragment, local);

    			transition_in(if_block7);
    			transition_in(if_block8);
    			transition_in(if_block9);

    			transition_in(files.$$.fragment, local);

    			current = true;
    		},

    		o: function outro(local) {
    			transition_out(errornotif.$$.fragment, local);
    			transition_out(if_block7);
    			transition_out(if_block8);
    			transition_out(if_block9);
    			transition_out(files.$$.fragment, local);
    			current = false;
    		},

    		d: function destroy(detaching) {
    			destroy_component(errornotif, detaching);

    			if (detaching) {
    				detach_dev(t0);
    				detach_dev(div0);
    			}

    			if (if_block0) if_block0.d();

    			if (detaching) {
    				detach_dev(t3);
    				detach_dev(h4);
    				detach_dev(t5);
    				detach_dev(div9);
    			}

    			if (if_block1) if_block1.d();
    			if (if_block2) if_block2.d();
    			if_block3.d();
    			if_block4.d();
    			if (if_block5) if_block5.d();
    			if (if_block6) if_block6.d();

    			destroy_each(each_blocks, detaching);

    			if (if_block7) if_block7.d();
    			if (if_block8) if_block8.d();
    			if (if_block9) if_block9.d();

    			if (detaching) {
    				detach_dev(t26);
    				detach_dev(div10);
    			}

    			ctx.files_binding(null);

    			destroy_component(files);

    			run_all(dispose);
    		}
    	};
    	dispatch_dev("SvelteRegisterBlock", { block, id: create_fragment$8.name, type: "component", source: "", ctx });
    	return block;
    }

    let stored = true;

    let tabcolor = 'has-text-grey-lighter';

    function instance$8($$self, $$props, $$invalidate) {
    	let $dataset_id, $datasetFiles;

    	validate_store(dataset_id, 'dataset_id');
    	component_subscribe($$self, dataset_id, $$value => { $dataset_id = $$value; $$invalidate('$dataset_id', $dataset_id); });
    	validate_store(datasetFiles, 'datasetFiles');
    	component_subscribe($$self, datasetFiles, $$value => { $datasetFiles = $$value; $$invalidate('$datasetFiles', $datasetFiles); });

    	
      
    // FIXME dataset_id is global on django template and not updated on save, change that!, FIXED???
    // FIXME files do not get updated
    if (init_dataset_id) { dataset_id.set(init_dataset_id); }

    let mssubcomp;
    let acquicomp;
    let prepcomp;
    let lccomp;
    let filescomp;
    let edited = false;
    let errors = {
      basics: [],
      sprep: [],
      acqui: [],
      lc: [],
    };
    let saveerrors = Object.assign({}, errors);
    let comperrors = [];


    let dsinfo = {
      datatype_id: '',
      project_id: '',
      ptype_id: '',
      storage_location: '',
      newprojectname: '',
      experiment_id: '',
      runname: '',
      pi: '',
      externalcontactmail: '',
      prefrac_id: '',
      prefrac_length: '',
      prefrac_amount: '',
      hiriefrange: '',
    };

    let pdata = {
      datasettypes: [],
      ptypes: [],
      projects: [],
      local_ptype_id: '',
      external_pis: [],
      prefracs: [],
      hirief_ranges: [],
    };

    let components = [];
    let isNewProject = false;
    let isNewExperiment = false;
    let isNewPI = false;
    let experiments = [];
    let tabshow = 'meta';

    async function getcomponents() {
      const result = await getJSON(`/datasets/show/components/${dsinfo.datatype_id}`);
      $$invalidate('components', components = result.components);
    }

    async function project_selected(event=false, saved=false) {
      if (dsinfo.project_id) {
        const result = await getJSON(`/datasets/show/project/${dsinfo.project_id}`);
        $$invalidate('dsinfo', dsinfo.pi = pdata.external_pis.filter(pi => pi.id === result.pi_id)[0], dsinfo);
        $$invalidate('dsinfo', dsinfo.ptype_id = result.ptype_id, dsinfo);
        $$invalidate('experiments', experiments = result.experiments);
        for (let key in projsamples) { delete(projsamples[key]);}    for (let [key, val] of Object.entries(result.projsamples)) { projsamples[key] = val; }
        $$invalidate('isNewProject', isNewProject = false);
      }
      if (!saved) {
        $$invalidate('dsinfo', dsinfo.experiment_id = '', dsinfo);
      }
      editMade();
    }

    function toggle_project() {
      $$invalidate('isNewProject', isNewProject = isNewProject === false);
    }

    function editMade() {
      $$invalidate('edited', edited = true);
      $$invalidate('errors', errors.basics = errors.basics.length ? validate() : [], errors);
    }

    async function fetchDataset() {
      let url = '/datasets/show/info/';
      url = $dataset_id ? url + $dataset_id : url;
    	const response = await getJSON(url);
      for (let [key, val] of Object.entries(response.projdata)) { $$invalidate('pdata', pdata[key] = val, pdata); }
      for (let [key, val] of Object.entries(response.dsinfo)) { $$invalidate('dsinfo', dsinfo[key] = val, dsinfo); }
      if ($dataset_id) {
        getcomponents();
        await project_selected(false, true); // false is event, true is saved param
        $$invalidate('isNewExperiment', isNewExperiment = false);
        $$invalidate('isNewPI', isNewPI = false);
      }
      $$invalidate('edited', edited = false);
    }

    function validate() {
    	comperrors = [];
    	const re = RegExp('^[a-z0-9-_]+$', 'i');
    	if ((isNewProject && !dsinfo.newprojectname) || (!isNewProject && !dsinfo.project_id)) {
    		comperrors.push('Project needs to be selected or created');
    	}
    	else if (isNewProject && dsinfo.newprojectname && !re.test(dsinfo.newprojectname)) {
    		comperrors.push('Project name may only contain a-z 0-9 - _');
    	}
    	if (!dsinfo.runname) {
    		comperrors.push('Run name is required');
    	}
    	else if (!re.test(dsinfo.runname)) {
    		comperrors.push('Run name may only contain a-z 0-9 - _');
    	}
      if (showMsdata && ((isNewExperiment && !dsinfo.newexperimentname) || (!isNewExperiment && !dsinfo.experiment_id))) {
    		comperrors.push('Experiment is required');
    	}
    	else if (showMsdata && isNewExperiment && dsinfo.newexperimentname && !re.test(dsinfo.newexperimentname)) {
    		comperrors.push('Experiment name may only contain a-z 0-9 - _');
    	}
      if (isExternal) {
    		if (!dsinfo.newpiname && !dsinfo.pi.id) {
    			comperrors.push('Need to select or create a PI');
    		}
    		if (!dsinfo.externalcontactmail) {
    			comperrors.push('External contact is required');
    		}
    	}
      // This is probably not possible to save in UI, button is disabled
    	if (!dsinfo.datatype_id) {
    		comperrors.push('Datatype is required');
    	}
      return comperrors;
    }

    async function save() {
      $$invalidate('errors', errors.basics = validate(), errors);
      if (showMsdata) { 
        let mserrors = mssubcomp.validate();
        $$invalidate('errors', errors.basics = [...errors.basics, ...mserrors], errors);
      }
      if (errors.basics.length === 0) { 
        let postdata = {
          dataset_id: $dataset_id,
          ptype_id: dsinfo.ptype_id,
          datatype_id: dsinfo.datatype_id,
          runname: dsinfo.runname,
          prefrac_id: dsinfo.prefrac_id,
          prefrac_length: dsinfo.prefrac_length,
          prefrac_amount: dsinfo.prefrac_amount,
          hiriefrange: dsinfo.hiriefrange,
        };
        if (isNewProject) {
          postdata.newprojectname = dsinfo.newprojectname;
        } else {
          postdata.project_id = dsinfo.project_id;
        }
        if (isNewExperiment) {
          postdata.newexperimentname = dsinfo.newexperimentname;
        } else {
          postdata.experiment_id = dsinfo.experiment_id;
        }
        if (isNewPI) {
          postdata.newpiname = dsinfo.newpiname;
        } else {
          postdata.pi_id = isExternal ? dsinfo.pi.id : pdata.internal_pi_id;
        }
        if (dsinfo.ptype_id !== pdata.local_ptype_id) {
          postdata.externalcontact = dsinfo.externalcontactmail;
        }
        const response = await postJSON('/datasets/save/project/', postdata);
        if ('error' in response) {
          $$invalidate('saveerrors', saveerrors.basics = [response.error, ...saveerrors.basics], saveerrors);
        } else {
      	  dataset_id.set(response.dataset_id);
          console.log($dataset_id);
          fetchDataset();
        }
      }
    }

    onMount(async() => {
      await fetchDataset();
    });

    function showMetadata() {
      $$invalidate('tabshow', tabshow = 'meta');
    }

    function showFiles() {
      $$invalidate('tabshow', tabshow = $dataset_id ? 'files' : tabshow);
    }

    	function select_change_handler() {
    		dsinfo.project_id = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function input_input_handler() {
    		dsinfo.newprojectname = this.value;
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function select_change_handler_1() {
    		dsinfo.ptype_id = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	const click_handler = (e) => $$invalidate('isNewPI', isNewPI = !isNewPI);

    	const click_handler_1 = (e) => $$invalidate('isNewPI', isNewPI = !isNewPI);

    	function select_change_handler_2() {
    		dsinfo.pi = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function input_input_handler_1() {
    		dsinfo.newpiname = this.value;
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function input_input_handler_2() {
    		dsinfo.externalcontactmail = this.value;
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function select_change_handler_3() {
    		dsinfo.datatype_id = select_value(this);
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function input_input_handler_3() {
    		dsinfo.runname = this.value;
    		$$invalidate('dsinfo', dsinfo);
    		$$invalidate('pdata', pdata);
    	}

    	function msdata_binding($$value) {
    		binding_callbacks[$$value ? 'unshift' : 'push'](() => {
    			$$invalidate('mssubcomp', mssubcomp = $$value);
    		});
    	}

    	function msdata_dsinfo_binding(value) {
    		dsinfo = value;
    		$$invalidate('dsinfo', dsinfo);
    	}

    	function msdata_isNewExperiment_binding(value_1) {
    		isNewExperiment = value_1;
    		$$invalidate('isNewExperiment', isNewExperiment);
    	}

    	function acquicomp_1_binding($$value) {
    		binding_callbacks[$$value ? 'unshift' : 'push'](() => {
    			$$invalidate('acquicomp', acquicomp = $$value);
    		});
    	}

    	function acquicomp_1_errors_binding(value_2) {
    		errors.acqui = value_2;
    		$$invalidate('errors', errors);
    	}

    	function prepcomp_1_binding($$value) {
    		binding_callbacks[$$value ? 'unshift' : 'push'](() => {
    			$$invalidate('prepcomp', prepcomp = $$value);
    		});
    	}

    	function prepcomp_1_errors_binding(value) {
    		errors.sprep = value;
    		$$invalidate('errors', errors);
    	}

    	function lcheck_binding($$value) {
    		binding_callbacks[$$value ? 'unshift' : 'push'](() => {
    			$$invalidate('lccomp', lccomp = $$value);
    		});
    	}

    	function lcheck_errors_binding(value) {
    		errors.lc = value;
    		$$invalidate('errors', errors);
    	}

    	function files_binding($$value) {
    		binding_callbacks[$$value ? 'unshift' : 'push'](() => {
    			$$invalidate('filescomp', filescomp = $$value);
    		});
    	}

    	$$self.$capture_state = () => {
    		return {};
    	};

    	$$self.$inject_state = $$props => {
    		if ('mssubcomp' in $$props) $$invalidate('mssubcomp', mssubcomp = $$props.mssubcomp);
    		if ('acquicomp' in $$props) $$invalidate('acquicomp', acquicomp = $$props.acquicomp);
    		if ('prepcomp' in $$props) $$invalidate('prepcomp', prepcomp = $$props.prepcomp);
    		if ('lccomp' in $$props) $$invalidate('lccomp', lccomp = $$props.lccomp);
    		if ('filescomp' in $$props) $$invalidate('filescomp', filescomp = $$props.filescomp);
    		if ('edited' in $$props) $$invalidate('edited', edited = $$props.edited);
    		if ('errors' in $$props) $$invalidate('errors', errors = $$props.errors);
    		if ('saveerrors' in $$props) $$invalidate('saveerrors', saveerrors = $$props.saveerrors);
    		if ('comperrors' in $$props) comperrors = $$props.comperrors;
    		if ('dsinfo' in $$props) $$invalidate('dsinfo', dsinfo = $$props.dsinfo);
    		if ('pdata' in $$props) $$invalidate('pdata', pdata = $$props.pdata);
    		if ('components' in $$props) $$invalidate('components', components = $$props.components);
    		if ('isNewProject' in $$props) $$invalidate('isNewProject', isNewProject = $$props.isNewProject);
    		if ('isNewExperiment' in $$props) $$invalidate('isNewExperiment', isNewExperiment = $$props.isNewExperiment);
    		if ('isNewPI' in $$props) $$invalidate('isNewPI', isNewPI = $$props.isNewPI);
    		if ('experiments' in $$props) $$invalidate('experiments', experiments = $$props.experiments);
    		if ('stored' in $$props) $$invalidate('stored', stored = $$props.stored);
    		if ('tabshow' in $$props) $$invalidate('tabshow', tabshow = $$props.tabshow);
    		if ('tabcolor' in $$props) tabcolor = $$props.tabcolor;
    		if ('showMsdata' in $$props) $$invalidate('showMsdata', showMsdata = $$props.showMsdata);
    		if ('isExternal' in $$props) $$invalidate('isExternal', isExternal = $$props.isExternal);
    		if ('$dataset_id' in $$props) dataset_id.set($dataset_id);
    		if ('$datasetFiles' in $$props) datasetFiles.set($datasetFiles);
    	};

    	let showMsdata, isExternal;

    	$$self.$$.update = ($$dirty = { components: 1, dsinfo: 1, pdata: 1 }) => {
    		if ($$dirty.components) { $$invalidate('showMsdata', showMsdata = components.indexOf('acquisition') > -1); }
    		if ($$dirty.dsinfo || $$dirty.pdata) { $$invalidate('isExternal', isExternal = dsinfo.ptype_id && dsinfo.ptype_id !== pdata.local_ptype_id); }
    	};

    	return {
    		mssubcomp,
    		acquicomp,
    		prepcomp,
    		lccomp,
    		filescomp,
    		edited,
    		errors,
    		saveerrors,
    		dsinfo,
    		pdata,
    		components,
    		isNewProject,
    		isNewExperiment,
    		isNewPI,
    		experiments,
    		tabshow,
    		getcomponents,
    		project_selected,
    		toggle_project,
    		editMade,
    		fetchDataset,
    		save,
    		showMetadata,
    		showFiles,
    		Object,
    		showMsdata,
    		isExternal,
    		$dataset_id,
    		$datasetFiles,
    		select_change_handler,
    		input_input_handler,
    		select_change_handler_1,
    		click_handler,
    		click_handler_1,
    		select_change_handler_2,
    		input_input_handler_1,
    		input_input_handler_2,
    		select_change_handler_3,
    		input_input_handler_3,
    		msdata_binding,
    		msdata_dsinfo_binding,
    		msdata_isNewExperiment_binding,
    		acquicomp_1_binding,
    		acquicomp_1_errors_binding,
    		prepcomp_1_binding,
    		prepcomp_1_errors_binding,
    		lcheck_binding,
    		lcheck_errors_binding,
    		files_binding
    	};
    }

    class App extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance$8, create_fragment$8, safe_not_equal, []);
    		dispatch_dev("SvelteRegisterComponent", { component: this, tagName: "App", options, id: create_fragment$8.name });
    	}
    }

    var app = new App({
    	target: document.querySelector('#appbox')
    });

    return app;

}());
//# sourceMappingURL=bundle.js.map
