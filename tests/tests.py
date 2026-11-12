import sys
import os

# parent folder holds libraries which needs to be included
sys.path.append(os.path.realpath('../lib'))

import simplejson as json
from simplejson import OrderedDict

import decimal
import unittest
import os
import sys

sys.path.append(os.path.realpath('../lib'))

import json5


class TestIssues(unittest.TestCase):
    def setUp(self):
        pass

    def test_ascii_issue_10(self):
        tmp_str = '{"tempstr":"\u2022"}'
        expected_output = '''{
  "tempstr": "\\u2022"
}'''
        obj = json.loads(tmp_str, object_pairs_hook=OrderedDict, parse_float=decimal.Decimal)
        tmp_str = json.dumps(obj, indent=2, ensure_ascii=True, sort_keys=False,
                             separators=(',', ': '),
                             use_decimal=True)
        self.assertEqual(tmp_str, expected_output)

    # issue 15
    def test_float_issue_15(self):
        tmp_str = '{"real":0.99}'
        expected_output = '''{
  "real": 0.99
}'''
        obj = json.loads(tmp_str, object_pairs_hook=OrderedDict, parse_float=decimal.Decimal)
        tmp_str = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False,
                             separators=(',', ': '),
                             use_decimal=True)
        self.assertEqual(tmp_str, expected_output)

    # issue 16
    def test_float_issue_16_1(self):
        tmp_str = '{ "float": 1.0 }'
        obj = json.loads(tmp_str, object_pairs_hook=OrderedDict, parse_float=decimal.Decimal)
        self.assertEqual(obj['float'], 1.0)
        tmp_str = json.dumps(obj, indent=0, ensure_ascii=False, sort_keys=False,
                             separators=(',', ': '),
                             use_decimal=True)
        self.assertEqual(tmp_str.split('\n')[1], '"float": 1.0')

    # issue 16
    def test_float_issue_16_2(self):
        tmp_str = '{"test1":0.99, "test2":"1.99", "test3":1.00000000001, "test4":1.99, "test5":1,' \
                  ' "test6":4.589999999999999999, "test7":1.0}'
        expected_output = '''{
  "test1": 0.99,
  "test2": "1.99",
  "test3": 1.00000000001,
  "test4": 1.99,
  "test5": 1,
  "test6": 4.589999999999999999,
  "test7": 1.0
}'''
        obj = json.loads(tmp_str, object_pairs_hook=OrderedDict, parse_float=decimal.Decimal)
        tmp_str = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False,
                             separators=(',', ': '),
                             use_decimal=True)
        self.assertEqual(tmp_str, expected_output)

    def test_compress_feature(self):
        tmp_str = '''{
  "real": 0.99
}'''
        expected_output = '{"real":0.99}'
        obj = json.loads(tmp_str, object_pairs_hook=OrderedDict, parse_float=decimal.Decimal)
        tmp_str = json.dumps(obj, ensure_ascii=False, sort_keys=False,
                             separators=(',', ':'),
                             use_decimal=True)
        self.assertEqual(tmp_str, expected_output)


class TestJson5(unittest.TestCase):
    def loads(self, text):
        return json.loads(json5.to_json(text), object_pairs_hook=OrderedDict,
                          parse_float=decimal.Decimal)

    def test_comments(self):
        text = '''{
            // line comment
            "a": 1, /* block
                       comment */
            "b": 2 // trailing
        }'''
        obj = self.loads(text)
        self.assertEqual(obj['a'], 1)
        self.assertEqual(obj['b'], 2)

    def test_single_quotes(self):
        obj = self.loads("{'a': 'it\\'s', 'b': 'say \"hi\"'}")
        self.assertEqual(obj['a'], "it's")
        self.assertEqual(obj['b'], 'say "hi"')

    def test_unquoted_keys(self):
        obj = self.loads('{foo: 1, $bar: 2, _baz: 3, "quoted": 4}')
        self.assertEqual(obj['foo'], 1)
        self.assertEqual(obj['$bar'], 2)
        self.assertEqual(obj['_baz'], 3)
        self.assertEqual(obj['quoted'], 4)

    def test_trailing_commas(self):
        obj = self.loads('{"a": [1, 2,], "b": {"c": 3,},}')
        self.assertEqual(obj['a'], [1, 2])
        self.assertEqual(obj['b'], OrderedDict([('c', 3)]))

    def test_hex_and_numbers(self):
        obj = self.loads('{a: 0xFF, b: +1.5, c: .5, d: 2., e: -3}')
        self.assertEqual(obj['a'], 255)
        self.assertEqual(obj['b'], decimal.Decimal('1.5'))
        self.assertEqual(obj['c'], decimal.Decimal('.5'))
        self.assertEqual(obj['d'], decimal.Decimal('2.'))
        self.assertEqual(obj['e'], -3)

    def test_multiline_single_quoted_string(self):
        obj = self.loads("{'a': 'line1\nline2'}")
        self.assertEqual(obj['a'], 'line1\nline2')

    def test_comment_markers_inside_strings(self):
        obj = self.loads('{"a": "http://x/*y", \'b\': "// not a comment"}')
        self.assertEqual(obj['a'], 'http://x/*y')
        self.assertEqual(obj['b'], '// not a comment')

    def test_special_values(self):
        obj = self.loads('{a: Infinity, b: -Infinity, c: NaN}')
        self.assertEqual(obj['a'], float('inf'))
        self.assertEqual(obj['b'], float('-inf'))
        self.assertTrue(obj['c'] != obj['c'])  # NaN

    def test_round_trip_strict_json(self):
        strict = '{"a": [1, 2], "b": {"c": true, "d": null}}'
        self.assertEqual(json5.to_json(strict), strict)

    def test_unterminated_string_raises(self):
        with self.assertRaises(ValueError):
            json5.to_json('{"a": "broken}')

    def test_unterminated_block_comment_raises(self):
        with self.assertRaises(ValueError):
            json5.to_json('{/* never ends')


class TestJson5Format(unittest.TestCase):
    def test_format_preserves_comments(self):
        text = '''{
// header comment
"a": 1, // trailing comment
/* block */ "b": [1, 2,],
}'''
        expected = '''{
    // header comment
    "a": 1, // trailing comment
    /* block */ "b": [
        1,
        2,
    ],
}'''
        self.assertEqual(json5.format(text, indent=4), expected)

    def test_format_normalizes_strings_and_numbers(self):
        text = "{'a': 'it\\'s', b: 0xFF, c: .5}"
        expected = '''{
    "a": "it's",
    b: 0xFF,
    c: .5
}'''
        self.assertEqual(json5.format(text, indent=4), expected)

    def test_format_empty_containers_and_nested(self):
        text = '{a: {}, b: [[]], c: {d: {e: 1}}}'
        expected = '''{
    a: {},
    b: [
        []
    ],
    c: {
        d: {
            e: 1
        }
    }
}'''
        self.assertEqual(json5.format(text, indent=4), expected)

    def test_format_multiline_block_comment(self):
        text = '{\n/* line1\nline2 */\n"a": 1\n}'
        expected = '''{
    /* line1
line2 */
    "a": 1
}'''
        self.assertEqual(json5.format(text, indent=4), expected)

    def test_format_comment_after_comma_stays_on_line(self):
        text = '{"a": 1, // one\n"b": 2}'
        expected = '''{
    "a": 1, // one
    "b": 2
}'''
        self.assertEqual(json5.format(text, indent=4), expected)

    def test_minify_preserves_comments(self):
        text = '''{
            // header
            "a": [1, .5,], /* inline */
        }'''
        expected = '''{
// header
"a":[1,.5,], /* inline */}'''
        self.assertEqual(json5.minify(text), expected)

    def test_minify_strict_json(self):
        self.assertEqual(json5.minify('{ "a" : [ 1 , 2 ] }'), '{"a":[1,2]}')

    def test_tokenize_signed_literals(self):
        kinds = [t[1] for t in json5.tokenize('{a: -Infinity, b: +NaN}')]
        self.assertEqual(kinds, ['{', 'a', ':', '-Infinity', ',', 'b', ':', '+NaN', '}'])


if __name__ == '__main__':
    unittest.main()
