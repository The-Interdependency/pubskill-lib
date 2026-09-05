import unittest

from pubskill_lib import schema


class SchemaTests(unittest.TestCase):
    def test_new_document_shape(self):
        document = schema.new_document("abc", "fixture")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["tool"], "pubskill-lib")
        self.assertEqual(document["source_pin"], "abc")
        self.assertEqual(document["target"]["path"], "fixture")
        self.assertEqual(document["findings"], [])
        schema.validate_document(document)

    def test_validate_accepts_valid_finding(self):
        document = schema.new_document("abc", "fixture")
        document["findings"].append(
            {
                "id": "F001",
                "surface": "docs",
                "claim": "README links to missing file",
                "evidence": "README.md:4",
                "class": "defect",
                "owner": "repository",
                "verified": False,
            }
        )
        schema.validate_document(document)

    def test_validate_rejects_unknown_class(self):
        document = schema.new_document("abc", "fixture")
        document["findings"].append(
            {
                "id": "F001",
                "surface": "docs",
                "claim": "x",
                "evidence": "y",
                "class": "bogus",
                "owner": "repository",
                "verified": False,
            }
        )
        with self.assertRaises(ValueError):
            schema.validate_document(document)

    def test_validate_rejects_unknown_surface(self):
        document = schema.new_document("abc", "fixture")
        document["findings"].append(
            {
                "id": "F001",
                "surface": "kitchen",
                "claim": "x",
                "evidence": "y",
                "class": "defect",
                "owner": "repository",
                "verified": False,
            }
        )
        with self.assertRaises(ValueError):
            schema.validate_document(document)

    def test_validate_defaults_missing_verified_to_false(self):
        document = schema.new_document("abc", "fixture")
        document["findings"].append(
            {
                "id": "F001",
                "surface": "docs",
                "claim": "x",
                "evidence": "y",
                "class": "defect",
                "owner": "repository",
            }
        )
        schema.validate_document(document)
        self.assertIs(document["findings"][0].get("verified", False), False)

    def test_validate_rejects_non_boolean_verified(self):
        document = schema.new_document("abc", "fixture")
        document["findings"].append(
            {
                "id": "F001",
                "surface": "docs",
                "claim": "x",
                "evidence": "y",
                "class": "defect",
                "owner": "repository",
                "verified": "yes",
            }
        )
        with self.assertRaises(ValueError):
            schema.validate_document(document)


if __name__ == "__main__":
    unittest.main()
