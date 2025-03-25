import setuptools

# Define your package files and directories
package_files = [
    "tetra/*.py",
    "tetra/core",
    "tetra/core/pool",
    "tetra/core/utils",
]

try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "Execute functions remotely"

setuptools.setup(
    name="tetra",
    version="0.0.0b1",
    author="Marut Pandya",
    author_email="pandyamarut@gmail.com",
    description="Execute functions remotely",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(include=['tetra', 'tetra.*']),  # Explicitly include tetra and all subpackages
    package_data={
        'tetra': ['*'],  # Include all files in tetra directory
    },
    include_package_data=True,  # Include non-Python files
    install_requires=[
        'grpcio',
        'grpcio-tools',
        'runpod',
        'cloudpickle',
        # Add other dependencies your package needs
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)