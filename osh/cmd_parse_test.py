#!/usr/bin/python3
"""
cmd_parse_test.py: Tests for cmd_parse.py
"""

import sys
import unittest

from asdl import py_meta

from core import ui
from core.word_node import DoubleQuotedPart
from core.id_kind import Id
from core.pool import Pool
from core import word

from osh import parse_lib
from osh.cmd_parse import CommandParser  # module under test
from osh.word_parse import WordParser


# TODO: Use parse_lib instead
def InitCommandParser(code_str):
  pool = Pool()
  line_reader, lexer = parse_lib.InitLexer(code_str)
  w_parser = WordParser(lexer, line_reader)
  c_parser = CommandParser(w_parser, lexer, line_reader)
  return pool, c_parser  # pool is returned for printing errors


def _assertParseMethod(test, code_str, method, expect_success=True):
  _, c_parser = InitCommandParser(code_str)
  m = getattr(c_parser, method)
  node = m()

  if node:
    if isinstance(node, py_meta.Obj):
      print(node)
    else:
      print(node.DebugString())
    if not expect_success:
      test.fail('Expected %r to fail ' % code_str)
  else:
    # TODO: Could copy PrintError from pysh.py
    err = c_parser.Error()
    print(err)
    pool = None
    ui.PrintError(err, pool, sys.stdout)
    if expect_success:
      test.fail('%r failed' % code_str)
  return node


def _assertParseCommandListError(test, code_str):
  pool, c_parser = InitCommandParser(code_str)
  node = c_parser.ParseCommandLine()
  if node:
    print('UNEXPECTED:')
    print(node)
    test.fail("Exepcted %r to fail" % code_str)
    return
  err = c_parser.Error()
  print(err)
  ui.PrintError(err, pool, sys.stdout)


#
# Successes
#
# (These differences might not matter, but preserve the diversity for now)

def assertParseSimpleCommand(test, code_str):
  return _assertParseMethod(test, code_str, 'ParseSimpleCommand')

def assertParsePipeline(test, code_str):
  return _assertParseMethod(test, code_str, 'ParsePipeline')

def assertParseAndOr(test, code_str):
  return _assertParseMethod(test, code_str, 'ParseAndOr')

def assertParseCommandLine(test, code_str):
  return _assertParseMethod(test, code_str, 'ParseCommandLine')

def assertParseCommandList(test, code_str):
  return _assertParseMethod(test, code_str, 'ParseCommandList')

def assertParseRedirect(test, code_str):
  return _assertParseMethod(test, code_str, 'ParseRedirect')

#
# Failures
#

#def assertFailSimpleCommand(test, code_str):
#  return _assertParseMethod(test, code_str, 'ParseSimpleCommand',
#      expect_success=False)
#
#def assertFailCommandLine(test, code_str):
#  return _assertParseMethod(test, code_str, 'ParseCommandLine',
#      expect_success=False)

def assertFailCommandList(test, code_str):
  return _assertParseMethod(test, code_str, 'ParseCommandList',
      expect_success=False)

#def assertFailRedirect(test, code_str):
#  return _assertParseMethod(test, code_str, 'ParseRedirect',
#      expect_success=False)


class SimpleCommandTest(unittest.TestCase):

  def testParseSimpleCommand1(self):
    node = assertParseSimpleCommand(self, 'ls foo')
    self.assertEqual(2, len(node.words), node.words)

    node = assertParseSimpleCommand(self, 'FOO=bar ls foo')
    self.assertEqual(2, len(node.words))
    self.assertEqual(1, len(node.more_env))

    node = assertParseSimpleCommand(self,
        'FOO=bar >output.txt SPAM=eggs ls foo')
    self.assertEqual(2, len(node.words))
    self.assertEqual(2, len(node.more_env))
    self.assertEqual(1, len(node.redirects))

    node = assertParseSimpleCommand(self,
        'FOO=bar >output.txt SPAM=eggs ls foo >output2.txt')
    self.assertEqual(2, len(node.words))
    self.assertEqual(2, len(node.more_env))
    self.assertEqual(2, len(node.redirects))

  def testMultipleGlobalAssignments(self):
    node = assertParseCommandList(self, 'ONE=1 TWO=2')
    self.assertEqual(Id.Node_Assign, node.id)
    self.assertEqual(2, len(node.bindings))
    self.assertEqual(0, len(node.words))

  def testExport(self):
    node = assertParseCommandList(self, 'export ONE=1 TWO=2 THREE')
    self.assertEqual(Id.Node_Assign, node.id)
    self.assertEqual(2, len(node.bindings))
    self.assertEqual(1, len(node.words))

  def testReadonly(self):
    node = assertParseCommandList(self, 'readonly ONE=1 TWO=2 THREE')
    self.assertEqual(Id.Node_Assign, node.id)
    self.assertEqual(2, len(node.bindings))
    self.assertEqual(1, len(node.words))

  def testOnlyRedirect(self):
    # This just touches the file
    node = assertParseCommandList(self, '>out.txt')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(0, len(node.words))
    self.assertEqual(1, len(node.redirects))

  def testParseRedirectInTheMiddle(self):
    node = assertParseCommandList(self, 'echo >out.txt 1 2 3')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(4, len(node.words))
    self.assertEqual(1, len(node.redirects))

  def testParseRedirectBeforeAssignment(self):
    # Write ENV to a file
    node = assertParseCommandList(self, '>out.txt PYTHONPATH=. env')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(1, len(node.words))
    self.assertEqual(1, len(node.redirects))
    self.assertEqual(1, len(node.more_env))

  def testParseAssignment(self):
    node = assertParseCommandList(self, 'local foo=bar spam eggs one=1')
    self.assertEqual(2, len(node.words), node.words)
    self.assertEqual(2, len(node.bindings))

    node = assertParseCommandList(self, 'foo=bar')
    self.assertEqual(0, len(node.words))
    self.assertEqual(1, len(node.bindings))

    # This is not valid since env isn't respected
    assertFailCommandList(self, 'FOO=bar local foo=$(env)')

  def testParseAdjacentDoubleQuotedWords(self):
    node = assertParseSimpleCommand(self, 'echo "one"two "three""four" five')
    self.assertEqual(4, len(node.words))


def assertHereDocToken(test, expected_token_val, node):
  #print(node)
  test.assertEqual(1, len(node.redirects))
  h = node.redirects[0]
  word_parts = h.arg_word.parts
  test.assertEqual(1, len(word_parts))  # 1 line, one literal part
  part1 = word_parts[0]
  test.assertGreater(len(part1.parts), 1, part1)
  test.assertEqual(expected_token_val, part1.parts[0].token.val)


class HereDocTest(unittest.TestCase):
  """NOTE: These ares come from tests/09-here-doc.sh, but add assertions."""

  def testUnquotedHereDoc(self):
    # Unquoted here docs use the double quoted context.
    node = assertParseCommandLine(self, """\
cat <<EOF
$v
"two
EOF
""")
    self.assertEqual(1, len(node.redirects))
    h = node.redirects[0]
    self.assertEqual(1, len(h.arg_word.parts))  # 1 double quoted part
    dq = h.arg_word.parts[0]
    self.assertTrue(isinstance(dq, DoubleQuotedPart))
    # 4 literal parts: VarSub, newline, right ", "two\n"
    self.assertEqual(4, len(dq.parts))
    self.assertEqual(True, h.do_expansion)

  def testQuotedDocs(self):
    # Quoted here doc
    node = assertParseCommandLine(self, """\
cat <<"EOF"
$v
"two
EOF
""")
    self.assertEqual(1, len(node.redirects))
    h = node.redirects[0]
    self.assertEqual(2, len(h.arg_word.parts))  # 2 literal parts
    self.assertEqual(False, h.do_expansion)

    node = assertParseCommandLine(self, """\
cat <<'EOF'
single-quoted: $var
EOF
""")
    self.assertEqual(1, len(node.redirects))
    h = node.redirects[0]
    self.assertEqual(1, len(h.arg_word.parts))  # 1 line, one literal part
    self.assertEqual(False, h.do_expansion)

    # \ escape
    node = assertParseCommandLine(self, r"""\
cat <<EO\F
single-quoted: $var
EOF
""")
    self.assertEqual(1, len(node.redirects))
    h = node.redirects[0]
    self.assertEqual(1, len(h.arg_word.parts))  # 1 line, one literal part
    self.assertEqual(False, h.do_expansion)

  def testLeadingTabs(self):
    node = assertParseCommandLine(self, """\
\tcat <<-EOF
\tone tab then foo: $foo
\tEOF
echo hi
""")
    assertHereDocToken(self, 'one tab then foo: ', node)

  def testHereDocInPipeline(self):
    # Pipe and command on SAME LINE
    node = assertParseCommandLine(self, """\
cat <<EOF | tac
PIPE 1
PIPE 2
EOF
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE 1\n', node.children[0])

    # Pipe command AFTER here doc
    node = assertParseCommandLine(self, """\
cat <<EOF |
PIPE 1
PIPE 2
EOF
tac
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE 1\n', node.children[0])

  def testTwoHereDocsInPipeline(self):
    # Pipeline with two here docs
    node = assertParseCommandList(self, """\
cat <<EOF1 | tac <<EOF2
PIPE A1
PIPE A2
EOF1
PIPE B1
PIPE B2
EOF2
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE A1\n', node.children[0])
    assertHereDocToken(self, 'PIPE B1\n', node.children[1])

  def testHereDocInAndOrChain(self):
    # || command AFTER here doc
    node = assertParseCommandLine(self, """\
cat <<EOF ||
PIPE 1
PIPE 2
EOF
echo hi
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE 1\n', node.children[0])

    # && and command on SAME LINE
    node = assertParseCommandLine(self, """\
cat <<EOF && echo hi
PIPE 1
PIPE 2
EOF
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE 1\n', node.children[0])

    node = assertParseCommandLine(self, """\
tac <<EOF1 && tac <<EOF2
PIPE A1
PIPE A2
EOF1
PIPE B1
PIPE B2
EOF2
echo
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE A1\n', node.children[0])
    assertHereDocToken(self, 'PIPE B1\n', node.children[1])

  def testHereDocInSequence(self):
    # PROBLEM: ParseCommandList vs ParseCommandLine
    # ParseCommandLine only used interactively.  ParseCommandList is used by
    # ParseFile.

    # command AFTER here doc
    node = assertParseCommandList(self, """\
cat <<EOF ;
PIPE 1
PIPE 2
EOF
echo hi
""")
    self.assertEqual(2, len(node.children), node.DebugString())
    assertHereDocToken(self, 'PIPE 1\n', node.children[0])

  def testHereDocInSequence2(self):
    # ; and command on SAME LINE
    node = assertParseCommandList(self, """\
cat <<EOF ; echo hi
PIPE 1
PIPE 2
EOF
""")
    self.assertEqual(2, len(node.children))
    assertHereDocToken(self, 'PIPE 1\n', node.children[0])

  def testCommandSubInHereDoc(self):
    node = assertParseCommandLine(self, """\
cat <<EOF
1 $(echo 2
echo 3) 4
EOF
""")
    self.assertEqual(1, len(node.words))
    self.assertEqual(1, len(node.redirects))


class ArrayTest(unittest.TestCase):

  def testArrayLiteral(self):
    # Empty array
    node = assertParseCommandList(self,
        'empty=()')
    self.assertEqual(['empty'], [k for k, v in node.bindings])
    self.assertEqual([], node.bindings[0][1].parts[0].words)  # No words
    self.assertEqual(Id.Node_Assign, node.id)

    # Array with 3 elements
    node = assertParseCommandList(self,
        'array=(a b c)')
    self.assertEqual(['array'], [k for k, v in node.bindings])
    self.assertEqual(3, len(node.bindings[0][1].parts[0].words))
    self.assertEqual(Id.Node_Assign, node.id)

    # Array literal can't come after word
    assertFailCommandList(self,
        'ls array=(a b c)')

    # Word can't come after array literal
    assertFailCommandList(self,
        'array=(a b c) ls')

    # Two array literals
    node = assertParseCommandList(self,
        'array=(a b c); array2=(d e f)')
    self.assertEqual(2, len(node.children))
    a2 = node.children[1]
    self.assertEqual(['array2'], [k for k, v in a2.bindings])


class RedirectTest(unittest.TestCase):

  def testParseRedirects1(self):
    node = assertParseSimpleCommand(self, '>out.txt cat 1>&2')
    self.assertEqual(1, len(node.words))
    self.assertEqual(2, len(node.redirects))

    node = assertParseSimpleCommand(self, ' cat <&3')
    self.assertEqual(1, len(node.redirects))

  def testParseFilenameRedirect(self):
    node = assertParseRedirect(self, '>out.txt cat')

  def testDescriptorRedirect(self):
    node = assertParseRedirect(self, '1>& 2 cat')

  def testHereRedirect(self):
    node = assertParseRedirect(self, """\
<<EOF cat
hi
EOF
""")

  def testHereRedirectStrip(self):
    node = assertParseRedirect(self, """\
<<-EOF cat
hi
EOF
""")

  def testParseRedirectList(self):
    node = assertParseRedirect(self, """\
<<EOF >out.txt cat
hi
EOF
""")

  def testParseCommandWithLeadingRedirects(self):
    node = assertParseSimpleCommand(self, """\
<<EOF >out.txt cat
hi
EOF
""")
    self.assertEqual(1, len(node.words))
    self.assertEqual(2, len(node.redirects))

  def testClobberRedirect(self):
    node = assertParseSimpleCommand(self, 'echo hi >| clobbered.txt')


class CommandParserTest(unittest.TestCase):

  def testParsePipeline(self):
    node = assertParsePipeline(self, 'ls foo')
    self.assertEqual(2, len(node.words))

    node = assertParsePipeline(self, 'ls foo|wc -l')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Op_Pipe, node.id)

    node = assertParsePipeline(self, '! echo foo | grep foo')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Op_Pipe, node.id)
    self.assertTrue(node.negated)

    node = assertParsePipeline(self, 'ls foo|wc -l|less')
    self.assertEqual(3, len(node.children))
    self.assertEqual(Id.Op_Pipe, node.id)

    # Should be an error
    _, c_parser = InitCommandParser('ls foo|')
    self.assertEqual(None, c_parser.ParsePipeline())
    print(c_parser.Error())

  def testParsePipelineBash(self):
    node = assertParseCommandList(self, 'ls | cat |& cat')
    self.assertEqual(Id.Op_Pipe, node.id)
    self.assertEqual([1], node.stderr_indices)

    node = assertParseCommandList(self, 'ls |& cat | cat')
    self.assertEqual(Id.Op_Pipe, node.id)
    self.assertEqual([0], node.stderr_indices)

    node = assertParseCommandList(self, 'ls |& cat |& cat')
    self.assertEqual(Id.Op_Pipe, node.id)
    self.assertEqual([0, 1], node.stderr_indices)

  def testParseAndOr(self):
    node = assertParseAndOr(self, 'ls foo')
    self.assertEqual(2, len(node.words))

    node = assertParseAndOr(self, 'ls foo|wc -l')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Op_Pipe, node.id)

    node = assertParseAndOr(self, 'ls foo || die')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Node_AndOr, node.id)

    node = assertParseAndOr(self, 'ls foo|wc -l || die')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Node_AndOr, node.id)

  def testParseCommand(self):
    _, c_parser = InitCommandParser('ls foo')
    node = c_parser.ParseCommand()
    self.assertEqual(2, len(node.words))
    print(node.DebugString())

    _, c_parser = InitCommandParser('func() { echo hi; }')
    node = c_parser.ParseCommand()
    print(node.DebugString())
    self.assertEqual(Id.Node_FuncDef, node.id)

  def testParseCommandLine(self):
    _, c_parser = InitCommandParser('ls foo 2>/dev/null')
    node = c_parser.ParseCommandLine()
    self.assertEqual(2, len(node.words))
    print(node.DebugString())

    _, c_parser = InitCommandParser('ls foo|wc -l')
    node = c_parser.ParseCommandLine()
    self.assertEqual(Id.Op_Pipe, node.id)
    print(node.DebugString())

    _, c_parser = InitCommandParser('ls foo|wc -l || die')
    node = c_parser.ParseCommandLine()
    self.assertEqual(Id.Node_AndOr, node.id)
    print(node.DebugString())

    _, c_parser = InitCommandParser('ls foo|wc -l || die; ls /')
    node = c_parser.ParseCommandLine()
    self.assertEqual(Id.Op_Semi, node.id)
    self.assertEqual(2, len(node.children))  # two top level things
    print(node.DebugString())

  def testParseCommandList(self):
    node = assertParseCommandList(self, 'ls foo')
    self.assertEqual(2, len(node.words))

    node = assertParseCommandList(self, 'ls foo|wc -l || die; ls /')
    self.assertEqual(Id.Op_Semi, node.id)
    self.assertEqual(2, len(node.children))

    node = assertParseCommandList(self, """\
ls foo | wc -l || echo fail ;
echo bar | wc -c || echo f2
""")
    self.assertEqual(Id.Op_Semi, node.id)
    self.assertEqual(2, len(node.children))

    # TODO: Check that we get (LIST (AND_OR (PIPELINE (COMMAND ...)))) here.
    # We want all levels.

  def testParseCase(self):
    # Empty case
    node = assertParseCommandLine(self, """\
case foo in
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

# TODO: Test all these.  Probably need to add newlines too.
# case foo esac  # INVALID
# case foo in esac
# case foo in foo) esac
# case foo in foo) ;; esac
# case foo in foo) echo hi ;; esac
# case foo in foo) echo hi; ;; esac

  def testParseCase2(self):
    node = assertParseCommandLine(self, """\
case word in
  foo) echo hi ;;
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

    node = assertParseCommandLine(self, """\
case word in foo) echo one-line ;; esac
""")
    self.assertEqual(Id.KW_Case, node.id)

    node = assertParseCommandLine(self, """\
case word in
  foo) echo foo ;;
  bar) echo bar ;;
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

    node = assertParseCommandLine(self, """\
case word in
  foo) echo foo ;;    # NO TRAILING ;; but trailing ;
  bar) echo bar ;
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

    node = assertParseCommandLine(self, """\
case word in
  foo) echo foo ;;    # NO TRAILING ;;
  bar) echo bar
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

  def testParseWhile(self):
    node = assertParseCommandList(self, """\
while true; do
  echo hi
  break
done
""")

    node = assertParseCommandList(self, """\
while true  # comment
do  # comment
  echo hi  # comment
  break  # comment
done  # comment
""")

  def testParseUntil(self):
    node = assertParseCommandList(self, """\
until false; do
  echo hi
  break
done
""")

  def testParseFor(self):
    node = assertParseCommandList(self, """\
for i in 1 2 3; do
  echo $i
done
""")
    self.assertEqual(3, len(node.iter_words))

    # Don't iterate over anything!
    node = assertParseCommandList(self, """\
for i in ; do
  echo $i
done
""")
    self.assertEqual(0, len(node.iter_words))
    self.assertEqual(False, node.do_arg_iter)

    # Iterate over the default
    node = assertParseCommandList(self, """\
for i; do echo $i; done
""")
    self.assertEqual(True, node.do_arg_iter)

    # Iterate over the default, over multiple lines
    node = assertParseCommandList(self, """\
for i
do
  echo $i
done
""")
    self.assertEqual(True, node.do_arg_iter)

  def testParseForExpression(self):
    node = assertParseCommandList(self, """\
for ((i=0; i<5; ++i)); do
  echo $i
done
""")
    self.assertEqual(Id.Arith_Equal, node.init.op_id)
    self.assertEqual(Id.Arith_Less, node.cond.op_id)
    self.assertEqual(Id.Arith_DPlus, node.update.op_id)
    self.assertEqual(1, len(node.children))

    # Now without the ; OR a newline
    node = assertParseCommandList(self, """\
for ((i=0; i<5; ++i)) do
  echo $i
done
""")
    self.assertEqual(Id.Arith_Equal, node.init.op_id)
    self.assertEqual(Id.Arith_Less, node.cond.op_id)
    self.assertEqual(Id.Arith_DPlus, node.update.op_id)
    self.assertEqual(1, len(node.children))

    node = assertParseCommandList(self, """\
for ((;;)); do
  echo $i
done
""")
    self.assertEqual(1, len(node.children))

  def testParseCommandSub(self):
    # Two adjacent command subs
    node = assertParseSimpleCommand(self, 'echo $(echo 12)$(echo 34)')
    self.assertEqual(2, len(node.words))

    # Two adjacent command subs, quoted
    node = assertParseSimpleCommand(self, 'echo "$(echo 12)$(echo 34)"')
    self.assertEqual(2, len(node.words))

  def testParseTildeSub(self):
    node = assertParseCommandList(self,
        "ls ~ ~root ~/src ~/src/foo ~root/src ~weird!name/blah!blah ")

  def testParseDBracket(self):
    node = assertParseCommandList(self, '[[ $# -gt 1 ]]')

    # Bash allows embedded newlines in some places, but not all
    node = assertParseCommandList(self, """\
[[ $# -gt 1 &&

foo ]]""")

    # Newline needs to be Id.Op_Newline!
    node = assertParseCommandList(self, """\
if [[ $# -gt 1 ]]
then
  echo hi
fi
""")

    # Doh, technically this works!
    # [[ =~ =~ =~ ]]; echo $?
    # 0

  def testParseDParen(self):
    node = assertParseCommandList(self, '(( 1 + 2 ))')

  def testParseDBracketRegex(self):
    node = assertParseCommandList(self, '[[ foo =~ foo ]]')
    self.assertEqual(Id.BoolBinary_EqualTilde, node.child.op_id)

    node = assertParseCommandList(self, '[[ foo =~ (foo|bar) ]]')
    self.assertEqual(Id.BoolBinary_EqualTilde, node.child.op_id)
    right = node.child.right
    self.assertEqual(5, len(right.parts))
    self.assertEqual('(', right.parts[0].token.val)

    # TODO: Implement BASH_REGEX_CHARS
    return
    node = assertParseCommandList(self, '[[ "< >" =~ (< >) ]]')
    self.assertEqual(Id.BoolBinary_EqualTilde, node.child.op_id)

    node = assertParseCommandList(self, '[[ "ba ba" =~ ([a b]+) ]]')
    self.assertEqual(Id.BoolBinary_EqualTilde, node.child.op_id)

  def testParseIf(self):
    node = assertParseCommandList(self, 'if true; then echo yes; fi')
    # Subshell in condition
    node = assertParseCommandList(self, 'if (true); then echo yes; fi')

  def testParseFunction(self):
    node = assertParseCommandList(self, 'foo() { echo hi; }')

    node = assertParseCommandList(self,
        'foo() ( echo hi )')
    node = assertParseCommandList(self,
        'foo() for i in x; do echo $i; done')

    # KSH FUNCTION
    node = assertParseCommandList(self, 'function foo { echo hi; }')
    node = assertParseCommandList(self, 'function foo () { echo hi; }')

    node = assertParseCommandList(self,
        'function foo() ( echo hi )')
    node = assertParseCommandList(self,
        'function foo() for i in x; do echo $i; done')

    # No () is OK here!
    node = assertParseCommandList(self,
        'function foo for i in x; do echo $i; done')

    # Redirects
    node = assertParseCommandList(self, 'foo() { echo hi; } 1>&2 2>/dev/null')
    self.assertEqual(2, len(node.redirects))
    self.assertEqual(1, len(node.children))

  def testParseKeyword(self):
    # NOTE: It chooses the longest match, which is Lit_Chars>
    node = assertParseCommandList(self, 'ifFOO')


class NestedParensTest(unittest.TestCase):
  """Test the hard $() and () nesting.

  Meanings of ):

  ( echo x )           # subshell (cmd_parse)
  echo $(echo x)       # command substitution (word_parse)
  (( ))                # end arith command (cmd_parse)
  $(( ))               # end arith sub (word_parse))
  a=(1 2 3)            # array literal and assoc array literal
  a[1*(2+3)]=x         # grouping in arith context
  func() { echo x ; }  # function def

  case x in x) echo x ;; esac     # case, with balanced or unbalanced
  case x in (x) echo x ;; esac
  """

  def testParseSubshell(self):
    node = assertParseCommandLine(self,
        '(cd /; echo PWD 1); echo PWD 2')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Op_Semi, node.id)

  def testParseBraceGroup(self):
    node = assertParseCommandLine(self,
        '{ cd /; echo PWD; }; echo PWD')
    self.assertEqual(2, len(node.children))
    self.assertEqual(Id.Op_Semi, node.id)

  def testUnquotedComSub(self):
    # CommandSubPart with two LiteralPart instances surrounding it
    node = assertParseSimpleCommand(self,
        'echo ab$(echo hi)cd ef')
    self.assertEqual(3, len(node.words))

  def testNestedComSub(self):
    node = assertParseSimpleCommand(self,
        'echo $(one$(echo two)one) three')
    self.assertEqual(3, len(node.words))

  def testArithSubWithin(self):
    # Within com sub
    node = assertParseSimpleCommand(self,
        'echo $(echo $((1+2)))')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))

    # Within subshell
    node = assertParseCommandList(self,
        '(echo $((1+2)))')
    self.assertEqual(Id.Node_Subshell, node.id)
    self.assertEqual(1, len(node.children))

  def testArithGroupingWithin(self):
    # Within com sub
    node = assertParseSimpleCommand(self,
        'echo $(echo $((1*(2+3))) )')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))

    # Within subshell
    node = assertParseCommandList(self,
        '(echo $((1*(2+3))) )')
    self.assertEqual(Id.Node_Subshell, node.id)
    self.assertEqual(1, len(node.children))

  def testLhsArithGroupingWithin(self):
    # NOTE: LHS not implemented yet
    return
    # Within com sub
    node = assertParseSimpleCommand(self,
        'echo $(a[1*(2+3)]=x)')
    self.assertEqual(2, len(node.words))

  def testFuncDefWithin(self):
    node = assertParseCommandList(self,
        'echo $(func() { echo hi; }; func)')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))

    node = assertParseCommandList(self,
        '(func() { echo hi; }; func)')
    self.assertEqual(Id.Node_Subshell, node.id)
    self.assertEqual(1, len(node.children))

  def testArrayLiteralWithin(self):
    node = assertParseCommandList(self,
        'echo $(array=(a b c))')
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))

    node = assertParseCommandList(self,
        '(array=(a b c))')
    self.assertEqual(Id.Node_Subshell, node.id)
    self.assertEqual(1, len(node.children))

  def testSubshellWithinComSub(self):
    node = assertParseCommandList(self,
        'echo one; echo $( (cd /; echo subshell_PWD); echo comsub_PWD); echo two')
    self.assertEqual(Id.Op_Semi, node.id)
    self.assertEqual(3, len(node.children))   # 3 echo statements

    # TODO: Need a way to test the literal value of a word
    #words = [w.UnquotedLiteralValue() for w in node.children[2].words]
    #print(words)

  def testCaseWithinComSub(self):
    node = assertParseCommandList(self,
        'echo $( case foo in one) echo comsub;; esac)')
    self.assertEqual(2, len(node.words))

    node = assertParseCommandList(self, """\
echo $(
case foo in one) echo comsub1;; esac
case bar in two) echo comsub2;; esac
)
""")
    self.assertEqual(2, len(node.words))

  def testComsubWithinCaseWithinComSub(self):
    # Comsub within case within comsub
    node = assertParseCommandList(self,
        'echo one; echo $( case one in $(echo one)) echo $(comsub);; esac ); echo two')
    self.assertEqual(Id.Op_Semi, node.id)
    # Top level should have 3 echo statements
    self.assertEqual(3, len(node.children))

  def testComSubWithinDoubleQuotes(self):
    # CommandSubPart with two LiteralPart instances surrounding it
    node = assertParseSimpleCommand(self,
        'echo "double $(echo hi) quoted" two')
    self.assertEqual(3, len(node.words))

  def testEmptyCaseWithinSubshell(self):
    node = assertParseCommandList(self, """\
( case foo in
  esac
)
""")
    self.assertEqual(Id.Node_Subshell, node.id)

  def testBalancedCaseWithin(self):
    # With leading ( in case.  This one doesn't cause problems!   We don't need
    # the MaybeUnreadOne() lexer hack.
    node = assertParseCommandList(self, """\
$( case foo in
  (one) echo hi ;;
  esac
)
""")
    self.assertEqual(Id.Node_Command, node.id)

    node = assertParseCommandList(self, """\
( case foo in
  (one) echo hi ;;
  esac
)
""")
    self.assertEqual(Id.Node_Subshell, node.id)

  def testUnbalancedCaseWithin(self):
    # With leading ( in case.  This one doesn't cause problems!   We don't need
    # the MaybeUnreadOne() lexer hack.
    node = assertParseCommandList(self, """\
$( case foo in
  one) echo hi ;;
  esac
)
""")
    self.assertEqual(Id.Node_Command, node.id)

    node = assertParseCommandList(self, """\
( case foo in
  one) echo hi ;;
  esac
)
""")
    self.assertEqual(Id.Node_Subshell, node.id)

  def testForExpressionWithin(self):
    # With leading ( in case.  This one doesn't cause problems!   We don't need
    # the MaybeUnreadOne() lexer hack.
    node = assertParseCommandList(self, """\
$( for ((i=0; i<3; ++i)); do
     echo hi
   done
)
""")
    self.assertEqual(Id.Node_Command, node.id)

    node = assertParseCommandList(self, """\
( for ((i=0; i<3; ++i)); do
    echo hi
  done
)
""")
    self.assertEqual(Id.Node_Subshell, node.id)


class RealBugsTest(unittest.TestCase):

  def testGitBug(self):
    # Original bug from git codebase.  Case in subshell.
    node = assertParseCommandList(self, """\
( cd "$PACKDIR" &&
  for e in $existing
  do
    case " $fullbases " in
      *" $e "*) ;;
      *) rm -f "$e.pack" "$e.idx" "$e.keep" ;;
    esac
  done
)
""")
    self.assertEqual(Id.Node_Subshell, node.id)

  def testParseCase3(self):
    # Bug from git codebase.  NOT a comment token.
    node = assertParseCommandLine(self, """\
case "$fd,$command" in
  3,#*|3,)
    # copy comments
    ;;
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

  def testGitComment(self):
    # ;# is a comment!  Gah.
    # Conclusion: Comments are NOT LEXICAL.  They are part of word parsing.

    node = assertParseCommandList(self, """\
. "$TEST_DIRECTORY"/diff-lib.sh ;# test-lib chdir's into trash
""")
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))

    # This is NOT a comment
    node = assertParseCommandList(self, """\
echo foo#bar
""")
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))
    _, s, _ = word.StaticEval(node.words[1])
    self.assertEqual('foo#bar', s)

    # This is a comment
    node = assertParseCommandList(self, """\
echo foo #comment
""")
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))
    _, s, _ = word.StaticEval(node.words[1])
    self.assertEqual('foo', s)

    # Empty comment
    node = assertParseCommandList(self, """\
echo foo #
""")
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(2, len(node.words))
    _, s, _ = word.StaticEval(node.words[1])
    self.assertEqual('foo', s)

  def testChromeIfSubshell(self):
    node = assertParseCommandList(self, """\
if true; then (
  echo hi
)
fi
""")
    self.assertEqual(Id.KW_If, node.id)

    node = assertParseCommandList(self, """\
while true; do {
  echo hi
  break
} done
""")
    self.assertEqual(Id.KW_While, node.id)

    node = assertParseCommandList(self, """\
if true; then (
  echo hi
) fi
""")
    self.assertEqual(Id.KW_If, node.id)

    # Related: two fi's in a row, found in Chrome configure.  Compound commands
    # are special; don't need newlines.
    node = assertParseCommandList(self, """\
if true; then
  if true; then
    echo hi
  fi fi
echo hi
""")
    self.assertEqual(Id.Op_Semi, node.id)

  def testBackticks(self):
    #return

    # Another empty command sub
    node = assertParseCommandList(self, """\
echo $()
""")

    # Simplest case
    node = assertParseCommandList(self, """\
echo ``
""")

    # Found in the wild.
    # Just a comment trick found in sandstorm
    node = assertParseCommandList(self, """\
cmd \
  flag `# comment` \
  flag2
""")

    # Empty should be allowed
    node = assertParseCommandList(self, """\
FOO="bar"`
    `"baz"
""")

  def testQuineDb(self):
    # Need to handle the DOLLAR_SQ lex state
    node = assertParseCommandList(self, r"""\
case foo in
$'\'')
  ret+="\\"\'
  ;;
esac
""")
    self.assertEqual(Id.KW_Case, node.id)

    node = assertParseCommandList(self, r"""\
$'abc\ndef'
""")
    self.assertEqual(Id.Node_Command, node.id)
    self.assertEqual(1, len(node.words))
    w = node.words[0]
    self.assertEqual(1, len(w.parts))
    p = w.parts[0]
    self.assertEqual(3, len(p.tokens))
    self.assertEqual(Id.Lit_Chars, p.tokens[0].id)
    self.assertEqual(Id.Lit_EscapedChar, p.tokens[1].id)
    self.assertEqual(Id.Lit_Chars, p.tokens[2].id)

  def testArithConstants(self):
    # Found in Gherkin
    node = assertParseCommandList(self, r"""\
 [[ -n "${marks[${tag_marker}002${cons_ptr}]}" ]];
""")
    # Dynamic constant
    node = assertParseCommandList(self, r"""\
echo $(( 0x$foo ))
""")


class ErrorLocationsTest(unittest.TestCase):

  def testNormal(self):
    #err = _assertParseCommandListError(self, 'ls <')

    err = _assertParseCommandListError(self, 'ls < <')
    return

    # Invalid words as here docs
    err = _assertParseCommandListError(self, 'cat << $(invalid here end)')
    err = _assertParseCommandListError(self, 'cat << $((1+2))')
    err = _assertParseCommandListError(self, 'cat << a=(1 2 3)')


if __name__ == '__main__':
  unittest.main()
