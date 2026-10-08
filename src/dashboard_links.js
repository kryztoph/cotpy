// Plotly strips file: links and some table renderers display anchor markup as text.
// Restore native SVG links after rendering, sorting, or scrolling table rows.
(function () {
    const graph = document.getElementById('{plot_id}');
    const svgNS = 'http://www.w3.org/2000/svg';
    const xlinkNS = 'http://www.w3.org/1999/xlink';

    function restoreLinks() {
        graph.querySelectorAll('.table text[data-unformatted]').forEach(function (cell) {
            let markup = cell.getAttribute('data-unformatted');
            if (markup.startsWith('&lt;a ')) {
                const decoder = document.createElement('textarea');
                decoder.innerHTML = markup;
                markup = decoder.value;
            }
            // Table wrapping can insert line breaks inside the opening tag.
            markup = markup.replace(/<br\s*\/?>/gi, ' ');
            const template = document.createElement('template');
            template.innerHTML = markup;
            const source = template.content.firstElementChild;
            if (!source || source.tagName !== 'A') return;
            const href = source.getAttribute('href');
            // Only generated sibling chart files are valid navigation targets.
            if (!href || !/^[^:/?#]+_interactive\.html$/.test(href)) return;
            const current = cell.querySelector('a');
            if (current && current.getAttributeNS(xlinkNS, 'href') === href &&
                    current.textContent === source.textContent &&
                    current.getAttribute('target') === '_self') return;
            const link = document.createElementNS(svgNS, 'a');
            link.setAttributeNS(xlinkNS, 'xlink:href', href);
            link.setAttribute('href', href);
            link.setAttribute('target', '_self');
            link.setAttribute('tabindex', '0');
            link.style.cursor = 'pointer';
            link.style.pointerEvents = 'all';
            cell.style.pointerEvents = 'all';
            link.style.fill = '#2563eb';
            link.style.textDecoration = 'underline';
            link.textContent = source.textContent;
            cell.replaceChildren(link);
        });
    }

    restoreLinks();
    graph.on('plotly_afterplot', restoreLinks);
    new MutationObserver(restoreLinks).observe(graph, {childList: true, subtree: true});
})();
