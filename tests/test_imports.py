import importlib


def test_core_modules_import_without_circular_error():
    importlib.import_module('src.character')
    importlib.import_module('src.goal')
    importlib.import_module('src.task')
    importlib.import_module('src.game')

