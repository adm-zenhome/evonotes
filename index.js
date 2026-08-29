const { spawn } = require('child_process');
const port = process.env.PORT || 8765;

console.log(`[Bridge] Launching Executive Voice OS (EvoNotes) on port ${port}...`);

const uvicorn = spawn('python3', [
    '-m', 'uvicorn',
    'dashboard.app:app',
    '--host', '0.0.0.0',
    '--port', String(port)
], {
    stdio: 'inherit',
    env: process.env
});

uvicorn.on('error', (err) => {
    console.error('[Bridge] Failed to start Python server:', err);
    process.exit(1);
});

uvicorn.on('exit', (code) => {
    console.log(`[Bridge] Python process exited with code ${code}`);
    process.exit(code || 0);
});
