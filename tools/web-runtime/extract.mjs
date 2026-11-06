// Parse source as data. Never import, evaluate or execute repository JavaScript.
import ts from 'typescript';
import { parseTemplate, BindingPipe } from '@angular/compiler';
import { readFileSync, writeFileSync } from 'node:fs';
const request = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const occurrences = [];
function add(key, path, line, kind) {
  if (occurrences.length >= 50000) throw Error('Usage budget exceeded');
  occurrences.push({ key, path, line, kind: key === null ? 'dynamic' : kind });
}
function template(text, path, offset = 0) {
  const parsed = parseTemplate(text, path, { preserveWhitespaces: true });
  if (parsed.errors?.length) throw Error('Invalid Angular template');
  const seen = new WeakSet();
  function walk(node) {
    if (!node || typeof node !== 'object' || seen.has(node)) return;
    seen.add(node);
    if (node instanceof BindingPipe && node.name === 'translate') {
      const key = typeof node.exp?.value === 'string' ? node.exp.value : null;
      const position = node.sourceSpan?.start ?? 0;
      add(key, path, offset + text.slice(0, position).split('\n').length, 'pipe');
    }
    for (const [key, value] of Object.entries(node)) {
      if (['sourceSpan', 'startSourceSpan', 'endSourceSpan', 'keySpan', 'valueSpan', 'nameSpan'].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(walk); else if (typeof value === 'object') walk(value);
    }
  }
  parsed.nodes.forEach(walk);
}
for (const [path, text] of Object.entries(request.files)) {
  if (path.endsWith('.html')) { template(text, path); continue; }
  const source = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  if (source.parseDiagnostics.length) throw Error('Invalid TypeScript');
  const services = new Set();
  // Resolve declaration identity, not just names: unrelated classes and shadowed
  // parameters can use the same field name without being TranslateService.
  const host = {
    ...ts.createCompilerHost({ noLib: true }),
    getSourceFile: file => file === path ? source : undefined,
    readFile: () => undefined, fileExists: () => false,
  };
  const program = ts.createProgram([path], { noLib: true, noResolve: true }, host);
  const checker = program.getTypeChecker();
  const receivers = new Set();
  const injectors = new Set();
  for (const statement of source.statements) {
    if (!ts.isImportDeclaration(statement) || statement.moduleSpecifier.text !== '@angular/core') continue;
    const named = statement.importClause?.namedBindings;
    if (named && ts.isNamedImports(named)) for (const el of named.elements) {
      if ((el.propertyName ?? el.name).text === 'inject') injectors.add(el.name.text);
    }
  }
  for (const statement of source.statements) {
    if (!ts.isImportDeclaration(statement) || statement.moduleSpecifier.text !== '@ngx-translate/core') continue;
    const named = statement.importClause?.namedBindings;
    if (named && ts.isNamedImports(named)) for (const el of named.elements) {
      if ((el.propertyName ?? el.name).text === 'TranslateService') services.add(el.name.text);
    }
  }
  function identify(node) {
    if (ts.isParameter(node) && node.type && ts.isTypeReferenceNode(node.type) && services.has(node.type.typeName.getText(source))) receivers.add(checker.getSymbolAtLocation(node.name));
    if ((ts.isPropertyDeclaration(node) || ts.isVariableDeclaration(node)) && node.initializer && ts.isCallExpression(node.initializer) && injectors.has(node.initializer.expression.getText(source)) && services.has(node.initializer.arguments[0]?.getText(source))) receivers.add(checker.getSymbolAtLocation(node.name));
    ts.forEachChild(node, identify);
  }
  identify(source);
  function walk(node) {
    if (ts.isPropertyAssignment(node) && node.name.getText(source) === 'template' && ts.isStringLiteralLike(node.initializer)) template(node.initializer.text, path, source.getLineAndCharacterOfPosition(node.initializer.getStart(source)).line);
    if (ts.isCallExpression(node)) {
      const expr = node.expression;
      let kind;
      if (ts.isIdentifier(expr) && expr.text === request.marker) kind = 'marker';
      if (ts.isPropertyAccessExpression(expr) && ['instant', 'get'].includes(expr.name.text)) {
        const receiver = expr.expression;
        const symbol = checker.getSymbolAtLocation(ts.isPropertyAccessExpression(receiver) ? receiver.name : receiver);
        if (symbol && receivers.has(symbol)) kind = expr.name.text;
      }
      if (kind) {
        const arg = node.arguments[0];
        const key = arg && ts.isStringLiteralLike(arg) ? arg.text : null;
        add(key, path, source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1, kind);
      }
    }
    ts.forEachChild(node, walk);
  }
  walk(source);
}
writeFileSync(process.argv[3], JSON.stringify({ occurrences }));
