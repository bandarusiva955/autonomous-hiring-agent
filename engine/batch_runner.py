"""
Batch runner - processes uploaded resumes in a background thread so large
batches never block (or time out) the web request.
"""
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Tuple

from .screening import extract_contact, score_resume

logger = logging.getLogger(__name__)

# At most two batches run at once per process; others queue.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='batch')


def _process_batch(store, batch_id: str, items: List[Tuple[str, str]], target: Dict,
                   components: Dict, parse_file: Callable[[str], str], tmp_dir: str):
    """Parse and score every file, saving each result as soon as it is ready."""
    extractor = components['extractor']
    matcher = components['matcher']
    scorer = components['scorer']
    try:
        for display_name, path in items:
            fallback_name = os.path.splitext(display_name)[0]
            try:
                text = parse_file(path)
                if not text or not text.strip():
                    raise ValueError('No readable text (scanned or image-only file?)')
                contact = extract_contact(text, fallback_name)
                result = score_resume(text, target, extractor, matcher, scorer)
                store.add_candidate(batch_id, display_name, name=contact['name'],
                                    email=contact['email'], result=result)
            except Exception as e:  # one bad file must not stop the batch
                logger.warning(f"Failed to process {display_name}: {e}")
                store.add_candidate(batch_id, display_name, status='error',
                                    error=str(e)[:200], name=fallback_name)
        store.finish_batch(batch_id, 'done')
    except Exception:
        logger.exception("Batch %s crashed", batch_id)
        store.finish_batch(batch_id, 'failed')
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def submit_batch(store, batch_id: str, items: List[Tuple[str, str]], target: Dict,
                 components: Dict, parse_file: Callable[[str], str], tmp_dir: str):
    """Queue a batch for background processing."""
    return _executor.submit(_process_batch, store, batch_id, items, target,
                            components, parse_file, tmp_dir)
