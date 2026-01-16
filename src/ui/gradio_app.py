import sys
from pathlib import Path

# Ensure project path is in sys.path
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from story_narrator import StoryGenerator, StoryPrompt

import gradio as gr

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def run_generate(theme, style, tone, length, voice_file, exaggeration, temperature, cfg_weight):
    try:
        # voice_file is already a filepath string in Gradio 6.x
        voice_path = voice_file if voice_file else None

        # Use RunPod by default (reads from .env USE_RUNPOD setting)
        narrator = StoryGenerator(llm_provider="gemini")

        prompt = StoryPrompt(
            theme=theme,
            style=style,
            tone=tone,
            length=length,
            target_audience="general",
            additional_details=None
        )

        import time
        out_name = OUTPUT_DIR / f"story_{int(time.time())}.wav"
        result = narrator.create_story_narration(
            story_prompt=prompt,
            voice_sample_path=voice_path,
            output_path=str(out_name),
            exaggeration=exaggeration,
            temperature=temperature,
            cfg_weight=cfg_weight,
            audio_format='wav',
            save_story_text=True,
            show_progress=True
        )

        return str(out_name), f"Success! Story generated and narrated."

    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        return None, error_msg


with gr.Blocks() as demo:
    gr.Markdown("# Story Narrator — Quick Test UI")

    with gr.Row():
        theme = gr.Textbox(label="Theme", value="A brave knight rescues a dragon")
        style = gr.Dropdown(label="Style", choices=['adventure','mystery','fantasy','sci-fi','horror','romance'], value='fantasy')
        tone = gr.Dropdown(label="Tone", choices=['engaging','suspenseful','lighthearted','dramatic','humorous'], value='lighthearted')
        length = gr.Dropdown(label="Length", choices=['short','medium','long'], value='short')

    voice = gr.Audio(type='filepath', label='Reference voice (.wav)')

    with gr.Row():
        exaggeration = gr.Slider(minimum=0.0, maximum=1.0, value=0.3, label='Exaggeration')
        temperature = gr.Slider(minimum=0.0, maximum=1.5, value=0.6, label='Temperature')
        cfg_weight = gr.Slider(minimum=0.0, maximum=1.0, value=0.3, label='CFG weight')

    btn = gr.Button("Generate & Narrate")
    out = gr.Audio(label="Output audio")
    status = gr.Textbox(label="Status")

    btn.click(fn=run_generate, inputs=[theme, style, tone, length, voice, exaggeration, temperature, cfg_weight], outputs=[out, status])


if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0', server_port=7860, share=False)
