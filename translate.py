#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

from openai import OpenAI
from typing import Iterable, Callable, TypeAlias
from pathlib import Path
from collections import OrderedDict

import tiktoken
import json

OPENAI_CLIENT = OpenAI(api_key='<FILL IN YOUR KEY>')

REF_LANGUAGE = 'en'
LANGUAGE_DIR = Path(__file__).parent.parent / 'language'

LANGCODE_NAMES = {
    'cs': 'Czech',
    'de': 'German',
    'en': 'English',
    'fr': 'French',
    'ru': 'Russian',
    'zh': 'Simplified Chinese',
}

LANG_TERMS = {
    "zh": {
        "widget": "部件",
        "utility": "设施",
    }
}

JsonNodeCallbackType: TypeAlias = Callable[[list[str], OrderedDict[str, str]], None]

class TranslationFile:
    def __init__(self, file: Path | None = None):
        self.content = OrderedDict()
        if (file is not None) and file.exists():
            try:
                with file.open() as f:
                    self.content:OrderedDict = json.load(f, object_pairs_hook=OrderedDict)
            except Exception as e:
                print('Failed to load', file, e)
        
    def walk(self, callback: JsonNodeCallbackType, ordered: bool):
        if ordered:
            self.__walk_content_ordered(self.content, callback, [])
        else:
            self.__walk_content_orderless(self.content, callback, [])
    
    def __walk_content_orderless(self, content: OrderedDict, callback: JsonNodeCallbackType, path: list[str]):
        direct_member = {}
        indirect_members = {}
        for key, value in content.items():
            assert isinstance(key, str)
            assert isinstance(value, str) or isinstance(value, dict)
            if isinstance(value, str):
                direct_member[key] = value
            elif isinstance(value, OrderedDict):
                indirect_members[key] = value
        if direct_member:
            callback(path, direct_member)
        for key, value in indirect_members.items():
            self.__walk_content_orderless(value, callback, path + [key])  
    
    def __walk_content_ordered(self, content: OrderedDict, callback: JsonNodeCallbackType, path: list[str]):
        for key, value in content.items():
            assert isinstance(key, str)
            assert isinstance(value, str) or isinstance(value, dict)
            if isinstance(value, str):
                callback(path, {key: value})
            elif isinstance(value, OrderedDict):
                self.__walk_content_ordered(value, callback, path + [key])

    def get(self, path: list[str], content: OrderedDict = None) -> OrderedDict[str, str]:
        node = self.content if content is None else content
        for key in path:
            if key not in node:
                node[key] = OrderedDict()
            node = node[key]
        return node

class TranslationFileSet:
    def __init__(self, langdir: Path):
        self.langdir = langdir
        self.data: dict[Path, TranslationFile] = {}
        if not langdir.exists():
            langdir.mkdir(parents=True, exist_ok=True)
        for name, tfile in self.__load():
            tfile.walk(lambda path, content: self.update(name, path, content), ordered=True)

    def __load(self) -> Iterable[tuple[Path, TranslationFile]]:
        for file in self.langdir.rglob("*.json"):
            yield file.relative_to(self.langdir), TranslationFile(file)

    def __iter__(self) -> Iterable[tuple[Path, TranslationFile]]:
        yield from self.data.items()

    def update(self, name: Path, path: list[str], content: OrderedDict[str, str]):
        if name not in self.data:
            self.data[name] = TranslationFile(name)
        node = self.data[name].get(path)
        node.update(content)

    def save(self, filename: Path|None = None):
        for name, tf in self.data.items():
            if filename is not None:
                if name != filename:
                    continue
            file = self.langdir / name
            if not file.parent.exists():
                file.parent.mkdir(parents=True, exist_ok=True)
            with file.open('w') as f:
                json.dump(tf.content, f, indent='\t', ensure_ascii=False)

    def fork(self, langdir: Path) -> 'TranslationFileSet':
        result = TranslationFileSet(self.langdir)
        result.langdir = langdir
        result.data.clear()
        for name, tf in self.data.items():
            result.data[name] = TranslationFile()
            result.data[name].content = tf.content.copy()
        return result

class GameLanguages:
    def __init__(self, language_dir: Path, ref_language: str):
        self.language_dir = language_dir
        self.ref_language = ref_language
        self.translations: dict[str, TranslationFileSet] = {}

    def translate_all(self):
        if not (self.language_dir / self.ref_language).exists():
            raise FileNotFoundError(f"Reference language directory '{self.ref_language}' not found in '{self.language_dir}'")
        self.translations[self.ref_language] = TranslationFileSet(self.language_dir / self.ref_language)
        for langcode in LANGCODE_NAMES:
            if langcode == self.ref_language:
                continue
            new_translation = self.translations[self.ref_language].fork(self.language_dir / langcode)
            for name, tf in new_translation.__iter__():
                def callback(path, content):
                    ok, output = translate(langcode, content)
                    if not ok:
                        print('Failed to translate:', name, path)
                    else:
                        new_translation.update(name, path, output)
                print('='*32, LANGCODE_NAMES[langcode], '->', name.as_posix())
                tf.walk(callback, ordered=False)    # optimization for mixed str|dict, reduce api calls. orders has been ensured
                new_translation.save(name)
            self.translations[langcode] = new_translation


# https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
# change the encoding_name as described above if you want to use a different model
tiktoken_encoder = tiktoken.get_encoding('o200k_base')  # gpt-4o, gpt-4o-mini
def count_token(string: str) -> int:
    num_tokens = len(tiktoken_encoder.encode(string))
    return num_tokens

def split_content(content: OrderedDict[str, str], max_tokens: int) -> list[OrderedDict[str, str]]:
    result = []
    current = OrderedDict()
    current_tokens = 0
    for key, value in content.items():
        tokens = count_token(json.dumps({key: value}, indent='\t', ensure_ascii=False))
        if current_tokens + tokens > max_tokens:
            result.append(current)
            current = OrderedDict()
            current_tokens = 0
        current[key] = value
        current_tokens += tokens
    if current:
        result.append(current)
    return result


def translate_internal(target_lang: str, content: OrderedDict[str, str]) -> tuple[bool, OrderedDict[str, str]]:
    print('Translating', len(content), 'lines to', LANGCODE_NAMES[target_lang], end='')

    ### DEBUG
    #return True, {k: "[+] "+v for k,v in content.items()}

    prompt_terms = ''
    if target_lang in LANG_TERMS:
        prompt_terms = f'Here are some terms for your reference: {json.dumps(LANG_TERMS[target_lang], ensure_ascii=False)}\n'

    system_message = {'role': 'system', 'content': 
        'You are now an i18n text translator.\n'

        'Keep translation concise and comprehensive. For polysemy words you are not sure, take a reasonable guess.\n'
        'If no idea at all, you can leave them as is.\n'

        f'{prompt_terms}\n'

        'The input will always be a valid JSON object with key:text.\n'
        f'You translate the text to {LANGCODE_NAMES[target_lang]},'
        'and always output valid JSON object in the same format, without any indent.'
        'the output keys will be exactly the same as input.'
    }
    completion = OPENAI_CLIENT.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            system_message,
            {'role': 'user', 'content': json.dumps(content, indent='\t')},
        ],
        response_format = { "type": "json_object" },
        temperature = 0.2,
        max_completion_tokens=16384,
    )
    result = completion.choices[0]
    # time.sleep(1.1) # OpenAI rate limit
    if result.finish_reason == 'stop':
        try:
            output = json.loads(result.message.content, object_pairs_hook=OrderedDict)
            return True, output
        except Exception as e:
            print('\tFailed to parse result:', e)
            return False, None
    print('\tunexpected API response:', result)
    return False, None

def translate(target_lang: str, large_content: OrderedDict[str, str]) -> tuple[bool, OrderedDict[str, str]]:
    # split large content into small pieces
    # max output token for gpt-4o-mini is 16384
    # we will limit our input to under 4000 tokens, in case of size inflation over languages
    splited_content = split_content(large_content, 4000)
    if len(splited_content) > 1:
        print('Split', len(large_content), 'lines into', len(splited_content), 'pieces')
    output = OrderedDict()
    for content in splited_content:
        ok, piece = translate_internal(target_lang, content)
        if not ok:
            print('\t[X] failed')
            return False, None
        print('\t[OK]')
        output.update(piece)
    # double check the keys, literal and order
    if output.keys() != large_content.keys():
        print('Keys mismatch:', output.keys(), large_content.keys())
        return False, None
    return True, output

gamelangs = GameLanguages(LANGUAGE_DIR, REF_LANGUAGE)
gamelangs.translate_all()
