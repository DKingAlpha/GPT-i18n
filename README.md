# GPT i18n Translator

This is the script I use to translate game text from English to other languages using OpenAI's GPT-4o-mini.

## Usage

1. Check the game [Beyond-All-Reason/language][BAR] for files layout and content format.
2. Edit global vars in `translate.py`.
3. Run `translate.py`
4. other languages will be generated in the output folder, preserving the original layout and order.

### Cost

$0.1 per language for all texts in [Beyond-All-Reason][BAR], around 320778 tokens.

[BAR]: https://github.com/beyond-all-reason/Beyond-All-Reason/tree/master/language

### Console Output Example

```sh
================================ Czech -> features.json
Translating 69 lines to Czech   [OK]
================================ Czech -> interface.json
Translating 1 lines to Czech    [OK]
Translating 1 lines to Czech    [OK]
Translating 8 lines to Czech    [OK]
Translating 10 lines to Czech   [OK]
Translating 7 lines to Czech    [OK]
Translating 2 lines to Czech    [OK]
...
```

### Supported File Schema

```json
{
    "$schema": "https://json-schema.org/draft-07/schema#",
    "title": "Translation",
    "type": "object",
    "additionalProperties": {
      "oneOf": [
        {
          "type": "string"
        },
        {
          "$ref": "#"
        }
      ]
    }
  }
```

#### Input File Example

```json
{
	"some_category": {
		"msg": "message content",
		"submsg": {
			"subsubmsg": "another message",
            "subsubmsg2": "another message"
		},
        "msg2": "message content 2"
    }
}
```
