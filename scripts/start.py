#!/usr/bin/env python

import argparse
import json
import os
import re
import sys
import urllib
import urllib.request
import yaml

VERSION = 'yinc.py version 0.2.0'


class CDir:
    def __init__(self, to):
        if to == '':
            self.origin = None
            return
        self.origin = os.getcwd()
        os.chdir(to)

    def back(self):
        if self.origin is None:
            return
        os.chdir(self.origin)


class SourceStream:
    def __init__(self, spec, writer):
        self.indent = ''
        self.first_indent = ''
        self.parent = None
        self.out = 0
        self.cdir = None
        self.spec = spec
        self.writer = writer

    def sub_stream(self, spec, indent, first_indent):
        p = self.parent
        while p is not None:
            if p.spec == spec:
                raise Exception('cyclic include detected.')
            p = p.parent
        sub = SourceStream(spec, self.writer)
        sub.indent = indent
        sub.first_indent = first_indent
        sub.parent = self
        return sub

    def get_content(self):
        if self.spec == '' or self.spec == '-':
            return tuple(os.stdin.read().splitlines())
        elif self.spec.startswith('$(shell ') and self.spec.endswith(')'):
            cmd = self.spec[8:-1]
            with os.popen(cmd) as f:
                lines = tuple(f.readlines())
            return lines
        elif self.spec.startswith('$(json ') and self.spec.endswith(')'):
            file = self.spec[7:-1]
            with open(file, 'r') as f:
                lines = f.read()
            data = json.loads(lines)
            self.cdir = CDir(os.path.dirname(file))
            return tuple(yaml.dump(data).splitlines())
        elif self.spec.startswith('http://') or self.spec.startswith('https://'):
            with urllib.request.urlopen(self.spec) as f:
                lines = tuple(f.read().decode().splitlines())
            return lines
        else:
            with open(self.spec, 'r') as f:
                lines = tuple(f.readlines())
            self.cdir = CDir(os.path.dirname(self.spec))
            return lines
        pass

    def write_indent(self, *args):
        if self.out == 0 and self.first_indent != '':
            self.write(self.first_indent)
        else:
            self.write(self.indent)
        for arg in args:
            self.write(arg)
        return

    def write(self, chunk):
        self.writer.write(chunk)
        self.out += len(chunk)
        return

    def process(self, args):
        lines = self.get_content()
        escaped_tag = f"({args.include_tag}|{args.replace_tag})".replace('!', '\\!')
        pat = re.compile(f'^(?P<indent>\\s*)((?P<text>[^\\s#]+)\\s+)?(?P<tag>{escaped_tag})\\s+(?P<spec>.+)$')
        for line in lines:
            line = line.rstrip()
            if line == '':
                continue
            m = pat.match(line)
            if m is not None:
                first_indent = ''
                new_indent = self.indent + m.group('indent')
                if m.group('text') and m.group('tag') == args.include_tag:
                    self.write_indent(m.group('indent'), m.group('text'))
                    if m.group('text') != '-':
                        self.write('\n')
                    new_indent += ' ' * args.indent_width
                    if m.group('text') == '-':
                        first_indent = ' '
                    pass
                sub = self.sub_stream(m.group('spec'), new_indent, first_indent)
                sub.process(args)
            else:
                self.write_indent(line, '\n')
            pass
        if self.cdir is not None:
            self.cdir.back()
        return


def process_all(args):
    if len(args.inputs) == 0:
        args.inputs += '-'
    nth = 0
    for input in args.inputs:
        if args.output_multi_documents and nth > 0:
            print('---')
        nth += 1
        SourceStream(input, sys.stdout).process(args)
    return


def exec():
    parser = argparse.ArgumentParser(prog='yinc.py', description='YAML Include')
    parser.add_argument('-w', '--indent-width', type=int, default=2, metavar='<n>', help='Indent width')
    parser.add_argument('-m', '--output-multi-documents', action='store_true', help='Output multiple documents')
    parser.add_argument('--include-tag', type=str, metavar='<tag>', default='!include', help='Specify include tag')
    parser.add_argument('--replace-tag', type=str, metavar='<tag>', default='!replace', help='Specify replace tag')
    parser.add_argument('-V', '--version', action='store_true', help="Show version information and exit")
    parser.add_argument('inputs', metavar='input', type=str, nargs='*', help='Input file(s)')
    args = parser.parse_args()
    if args.version:
        print(VERSION)
        sys.exit(0)
    process_all(args)


if __name__ == '__main__':
    exec()
