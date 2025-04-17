import asyncio
import base64
import io
from PIL import Image
from tetra import remote, LiveServerless

# Configuration for a GPU resource
sd_config = LiveServerless(
    gpuIds="NVIDIA GeForce RTX 4090",
    workersMax=1,
    name="example_image_gen_server",
)


@remote(
    resource_config=sd_config,
    dependencies=["diffusers", "transformers", "torch", "accelerate", "safetensors"],
)
def generate_image(
    prompt,
    negative_prompt="",
    width=512,
    height=512,
    num_inference_steps=30,
    guidance_scale=7.5,
):
    """Generate an image using Stable Diffusion."""
    import torch
    from diffusers import StableDiffusionPipeline
    import io
    import base64
    from PIL import Image
    from pathlib import Path
    import os

    # File-based model caching to avoid reloading
    model_path = Path("/tmp/stable_diffusion_model")
    os.makedirs(model_path, exist_ok=True)

    # Load pipeline
    print("Loading Stable Diffusion pipeline...")
    pipeline = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16,
        cache_dir=str(model_path),
        local_files_only=(model_path / "snapshots").exists(),
    )

    # Move to GPU
    pipeline = pipeline.to("cuda")

    # Generate image
    print(f"Generating image for prompt: '{prompt}'")
    image = pipeline(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
    ).images[0]

    # Convert to base64
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return {"image": img_str, "prompt": prompt, "dimensions": f"{width}x{height}"}


async def main():
    # Generate an image
    print("Generating image...")
    result = await generate_image(
        prompt="Superman and batman fighting with spiderman",
        negative_prompt="blurry, distorted, low quality, text, watermark",
        width=768,
        height=512,
    )

    # Save the image
    img_data = base64.b64decode(result["image"])
    image = Image.open(io.BytesIO(img_data))

    # Save to file
    output_file = "knight.png"
    image.save(output_file)
    print(f"Image saved to {output_file}")
    print(f"Prompt: {result['prompt']}")
    print(f"Dimensions: {result['dimensions']}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
