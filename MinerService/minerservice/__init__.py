from minerworkers import app

from ._version import version

__all__ = [
    'version'
]

app.autodiscover_tasks(['dataminer', 'marketbreadth'], force=True)
