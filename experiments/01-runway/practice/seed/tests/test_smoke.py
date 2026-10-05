import unittest


class Smoke(unittest.TestCase):
    def test_package_imports(self):
        import hours  # noqa: F401


if __name__ == "__main__":
    unittest.main()
