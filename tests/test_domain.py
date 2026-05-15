import unittest


class DomainSmokeTest(unittest.TestCase):
    def test_package_imports(self):
        import medidiet

        self.assertEqual(medidiet.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
