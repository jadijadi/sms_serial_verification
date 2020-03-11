import unittest
import import_db as idb


class TestImportDb(unittest.TestCase):
    def test_normalize_string(self):
        self.assertEqual(idb.normalize_string('abc12', 10), 'ABC0000012')
        self.assertEqual(idb.normalize_string('abc00١٢', 10), 'ABC0000012')

    def test_get_database_connection(self):
        try:
            idb.get_database_connection()
        except Exception as err:
            self.fail(f"Error in connect to db: {err}")

    def test_import_database_from_excel(self):
        self.assertEqual(
            idb.import_database_from_excel('./test_excel.xlsx'),
            (2, 2))

    def test_db_check(self):
        self.assertNotEqual(idb.db_check(), [])



if __name__ == '__main__':
    unittest.main()
