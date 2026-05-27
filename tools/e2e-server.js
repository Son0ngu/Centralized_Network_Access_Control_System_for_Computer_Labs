const { existsSync } = require('fs');
const { join, resolve } = require('path');
const { spawn, spawnSync } = require('child_process');

const rootDir = resolve(__dirname, '..');
const serverDir = join(rootDir, 'server');
const baseURL = new URL(process.env.E2E_BASE_URL || 'http://127.0.0.1:5000');

const env = {
  ...process.env,
  HOST: process.env.HOST || baseURL.hostname,
  PORT: process.env.PORT || baseURL.port || (baseURL.protocol === 'https:' ? '443' : '80'),
};

function commandExists(command, args = ['--version']) {
  const result = spawnSync(command, args, { stdio: 'ignore', shell: false });
  return !result.error && result.status === 0;
}

function findPython() {
  if (process.env.E2E_PYTHON) {
    return { command: process.env.E2E_PYTHON, args: ['app.py'] };
  }

  const localVenv = join(rootDir, '.venv', 'Scripts', 'python.exe');
  if (existsSync(localVenv)) {
    return { command: localVenv, args: ['app.py'] };
  }

  const commands = [
    { command: 'python', args: ['app.py'], probeArgs: ['--version'] },
    { command: 'python3', args: ['app.py'], probeArgs: ['--version'] },
    { command: 'py', args: ['-3', 'app.py'], probeArgs: ['-3', '--version'] },
  ];
  for (const candidate of commands) {
    if (commandExists(candidate.command, candidate.probeArgs)) {
      return { command: candidate.command, args: candidate.args };
    }
  }

  return null;
}

const python = findPython();
if (!python) {
  console.error(
    'Cannot start Flask server: no Python runtime found. ' +
    'Set E2E_SKIP_WEBSERVER=1 to test an already-running server, or set E2E_PYTHON.'
  );
  process.exit(1);
}

const child = spawn(python.command, python.args, {
  cwd: serverDir,
  env,
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code || 0);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    child.kill(signal);
  });
}
