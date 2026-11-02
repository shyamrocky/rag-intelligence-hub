"""Actual Streamlit AppTest timing and release-switch observations, not a browser."""

import json
import resource
import sys
from pathlib import Path
from time import perf_counter

from streamlit.testing.v1 import AppTest

from rag_hub.chunk_dashboard import load_chunk_catalog
from rag_hub.dashboard_ui import load_dashboard
from rag_hub.operational_selection import DURABLE, HISTORICAL


def main(output):
    root = Path.cwd().resolve()
    output = output.resolve()
    if output.exists() or not output.is_relative_to(root / 'workspace'):
        raise ValueError('new_private_report_path_required')
    app = AppTest.from_file(str(root / 'apps/ingestion_dashboard/app.py'), default_timeout=240)
    app.session_state['view'] = 'Chunk Inspector'
    start = perf_counter()
    app.run()
    first = perf_counter() - start
    assert not app.exception and not app.error
    results = []
    for selector in [HISTORICAL, DURABLE]:
        start = perf_counter()
        app.selectbox(key='operational_release').set_value(selector).run()
        selection = perf_counter() - start
        assert not app.exception and not app.error
        assert app.text_input(key='chunk_entered').value == ''
        start = perf_counter()
        app.run()
        warm = perf_counter() - start
        data = load_dashboard(str(root), selector=selector)
        cat = load_chunk_catalog(str(root), selector, _data=data)
        row = cat.list_chunks('C01', limit=1)['items'][0]
        del data, cat
        start = perf_counter()
        app.text_input(key='chunk_entered').set_value(row['chunk_id']).run()
        chunk = perf_counter() - start
        assert not app.exception and not app.error
        assert any(h.value == 'Complete authorized parent' for h in app.subheader)
        results.append({'selector': selector, 'selection_seconds': selection,
                        'warm_rerender_seconds': warm, 'open_chunk_render_seconds': chunk,
                        'selected_chunk_cleared_on_mode_entry': True,
                        'complete_parent_rendered': True})
    result = {'method': 'Actual Streamlit AppTest, not browser verification',
              'initial_app_and_historical_catalog_seconds': first, 'modes': results,
              'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'note': 'Historical reselect is already warm; durable selection constructs a new cold stack. '
                      'Observed local wall-clock timings include validation and UI work; not service SLAs.'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
