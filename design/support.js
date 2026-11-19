/**
 * StitchSense / Claude Design Canvas Local Runtime
 * Implements DCLogic and renders <x-dc>, <sc-for>, <sc-if>, and {{...}} template bindings.
 */

window.DCLogic = class DCLogic {
  constructor() {}
  renderVals() {
    return {};
  }
};

(function () {
  function evalInScope(rawExpr, scope) {
    let expr = (rawExpr || '').trim();
    if (expr.startsWith('{{') && expr.endsWith('}}')) {
      expr = expr.slice(2, -2).trim();
    }
    if (expr === 'true') return true;
    if (expr === 'false') return false;
    if (expr === 'null') return null;
    if (expr === 'undefined') return undefined;
    if (!isNaN(expr) && expr !== '') return Number(expr);

    try {
      const keys = Object.keys(scope);
      const vals = Object.values(scope);
      const fn = new Function(...keys, `return (${expr});`);
      return fn(...vals);
    } catch (e) {
      try {
        const parts = expr.split('.');
        let val = scope;
        for (const p of parts) {
          if (val == null) return '';
          val = val[p];
        }
        return val !== undefined ? val : '';
      } catch (err) {
        return '';
      }
    }
  }

  function interpolate(str, scope) {
    if (typeof str !== 'string') return str;
    return str.replace(/\{\{([^{}]+)\}\}/g, (_, expr) => {
      const res = evalInScope(expr, scope);
      return res === undefined || res === null ? '' : String(res);
    });
  }

  function renderTree(node, scope) {
    if (!node) return;

    if (node.nodeType === Node.TEXT_NODE) {
      if (node.nodeValue && node.nodeValue.includes('{{')) {
        node.nodeValue = interpolate(node.nodeValue, scope);
      }
      return;
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      const tag = node.tagName.toLowerCase();

      if (tag === 'sc-for') {
        const listExpr = node.getAttribute('list') || '';
        const asVar = node.getAttribute('as') || 'item';
        const items = evalInScope(listExpr, scope);

        const frag = document.createDocumentFragment();
        if (Array.isArray(items)) {
          items.forEach((item, index) => {
            const childScope = Object.assign({}, scope, {
              [asVar]: item,
              [`${asVar}Index`]: index,
            });
            for (let i = 0; i < node.childNodes.length; i++) {
              const clone = node.childNodes[i].cloneNode(true);
              renderTree(clone, childScope);
              frag.appendChild(clone);
            }
          });
        }
        if (node.parentNode) {
          node.parentNode.replaceChild(frag, node);
        }
        return;
      }

      if (tag === 'sc-if') {
        const testExpr = node.getAttribute('value') || node.getAttribute('test') || '';
        const testVal = evalInScope(testExpr, scope);

        if (testVal) {
          const frag = document.createDocumentFragment();
          for (let i = 0; i < node.childNodes.length; i++) {
            const clone = node.childNodes[i].cloneNode(true);
            renderTree(clone, scope);
            frag.appendChild(clone);
          }
          if (node.parentNode) {
            node.parentNode.replaceChild(frag, node);
          }
        } else {
          if (node.parentNode) {
            node.parentNode.removeChild(node);
          }
        }
        return;
      }

      // Normal element: process attributes
      const attrs = Array.from(node.attributes);
      for (const attr of attrs) {
        if (attr.value && attr.value.includes('{{')) {
          const newVal = interpolate(attr.value, scope);
          node.setAttribute(attr.name, newVal);
        }
      }

      // Process children
      const children = Array.from(node.childNodes);
      for (const child of children) {
        renderTree(child, scope);
      }
    }
  }

  function init() {
    // 1. Move <helmet> content to <head>
    const helmet = document.querySelector('helmet');
    if (helmet) {
      while (helmet.firstChild) {
        document.head.appendChild(helmet.firstChild);
      }
      helmet.remove();
    }

    // 2. Ensure default styles for custom element <x-dc>
    let defaultStyle = document.getElementById('dc-default-style');
    if (!defaultStyle) {
      defaultStyle = document.createElement('style');
      defaultStyle.id = 'dc-default-style';
      defaultStyle.textContent = `
        x-dc { display: block; width: 100%; min-height: 100vh; }
        sc-for, sc-if { display: contents; }
      `;
      document.head.appendChild(defaultStyle);
    }

    // 3. Find and execute Component script
    const scriptEl = document.querySelector('script[type="text/x-dc"][data-dc-script]');
    let data = {};
    if (scriptEl) {
      try {
        const code = scriptEl.textContent;
        const fn = new Function('DCLogic', `${code}\nreturn typeof Component !== "undefined" ? Component : null;`);
        const CompClass = fn(window.DCLogic);
        if (CompClass) {
          const comp = new CompClass();
          if (typeof comp.renderVals === 'function') {
            data = comp.renderVals() || {};
          }
        }
      } catch (err) {
        console.error('[Claude Design support.js] Failed to execute component script:', err);
      }
    }

    // 4. Render <x-dc>
    const xdc = document.querySelector('x-dc');
    if (xdc) {
      renderTree(xdc, data);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
