from setuptools import setup, find_packages

setup(
    name="voxcode",
    version="1.0.0",
    description="Hands-free voice interface for aider — a terminal AI coding agent",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "aider-chat>=0.60.0",         # the terminal coding agent being wrapped
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "webrtcvad-wheels>=2.0.10",   # prebuilt binaries — no C compiler needed
        "groq>=0.9.0",
        "rich>=13.7.0",
        "click>=8.1.0",
        "python-dotenv>=1.0.0",
        "pynput>=1.7.6",
    ],
    extras_require={
        "local-stt": ["faster-whisper>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "voxcode=voice_agent.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
