#!/usr/bin/env python3
"""One fused Fast reference; no MLX import or generation without explicit execution gate."""
import argparse
from contextlib import closing
import gc
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import diagnostic as diagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--root-go', choices=['ROOT_GO'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.execute or args.root_go != 'ROOT_GO' or args.output is None or args.output.exists():
        raise ValueError('Reference requires explicit ROOT_GO and a new output')
    diagnostic.check()
    from tutor_app.stem_training import configure_ssd_caches, ResourceMonitor, TrainingStopped
    from tutor_app.stem_training_eval import VisibleTokens
    configure_ssd_caches()
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler, make_logits_processors
    mx.set_memory_limit(13*1024**3)
    mx.reset_peak_memory()
    resources = ResourceMonitor()
    result = dict(id='python', public_final='', finish_reason=None, error=None, thinking_observed=False)
    started = time.monotonic()
    model, tokenizer, visible, response = None, None, None, None
    first = None
    try:
        model, tokenizer = load(str(diagnostic.MODEL), lazy=False,
                               tokenizer_config={'trust_remote_code': False, 'local_files_only': True})
        model.eval(); mx.eval(model.parameters())
        if mx.get_peak_memory() > 14*1024**3:
            raise MemoryError('Python observed peak exceeds 14 GiB')
        prompt = tokenizer.apply_chat_template([{'role':'user','content':diagnostic.USER}], tokenize=False,
                                                add_generation_prompt=True, enable_thinking=False)
        visible = VisibleTokens(False, tokenizer.convert_tokens_to_ids('<think>'),
                                tokenizer.convert_tokens_to_ids('</think>'), set(tokenizer.eos_token_ids))
        mx.random.seed(42)
        with closing(stream_generate(model, tokenizer, prompt=prompt, max_tokens=512,
            sampler=make_sampler(temp=.7, top_p=.8, top_k=20),
            logits_processors=make_logits_processors(presence_penalty=1.5, presence_context_size=1024))) as stream:
            for response in stream:
                resources.check()
                if time.monotonic()-started > 45:
                    raise TimeoutError('Python 45-second condition deadline')
                if mx.get_peak_memory() > 14*1024**3:
                    raise MemoryError('Python observed peak exceeds 14 GiB')
                before = len(visible.tokens)
                visible.feed(int(response.token))
                if first is None and len(visible.tokens) > before:
                    first = time.monotonic()-started
                # Preserve only public content; no token IDs or private text leave this process.
                result['public_final'] = tokenizer.decode(visible.tokens, skip_special_tokens=True)
                diagnostic.write(args.output, result)
        result['finish_reason'] = response.finish_reason if response else None
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        if isinstance(exc, (MemoryError, TrainingStopped)):
            result['fatal_resource'] = result['error']
    finally:
        result.update(seconds=time.monotonic()-started, first_public_seconds=first,
                      peak_bytes=mx.get_peak_memory(), resources=resources.latest,
                      final_tokens=len(visible.tokens) if visible else 0,
                      thinking_observed=bool(visible.reasoning_tokens) if visible else False)
        diagnostic.write(args.output, result)
        del model
        gc.collect(); mx.clear_cache()


if __name__ == '__main__':
    main()
