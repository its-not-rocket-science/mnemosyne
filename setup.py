from setuptools import setup, find_packages

setup(
    name='mnemosyne',
    version='0.1.0',
    author='[Paul Schleifer]',
    author_email='paul_schleifer@hotmail.com]',
    description='An autonomous knowledge extraction and continual learning system using LLMs and knowledge graphs.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/its-not-rocket-science/mnemosyne',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'python>=3.9',
        'wikiextractor',
        'openai',
        'langchain',
        'neo4j',
        'py2neo',
        'beautifulsoup4',
        'lxml',
        'ray',
        'tqdm',
        'pandas',
        'numpy',
        'loguru',
        'transformers',
        'sentence-transformers',
        'jupyter',
        'ipykernel'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)
