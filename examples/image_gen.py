import asyncio
import os
import base64
import io
from PIL import Image
from tetra import remote, get_global_client

# Configuration for a GPU resource
sd_config = {
    "api_key": os.environ.get("RUNPOD_API_KEY"),
    "template_id": "jizsa65yn0",  # Replace with your template ID
    "gpu_ids": "AMPERE_48",  # Choose an appropriate GPU type
    "workers_min": 1,
    "workers_max": 1,
    "name": "stable-diffusion-server",
}


@remote(
    resource_config=sd_config,
    resource_type="serverless",
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
    import os

    # File-based model caching to avoid reloading
    model_path = "/tmp/stable_diffusion_model"
    os.makedirs(model_path, exist_ok=True)

    # Load pipeline
    print("Loading Stable Diffusion pipeline...")
    pipeline = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16,
        cache_dir=model_path,
        local_files_only=os.path.exists(os.path.join(model_path, "snapshots")),
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
    asyncio.run(main())
