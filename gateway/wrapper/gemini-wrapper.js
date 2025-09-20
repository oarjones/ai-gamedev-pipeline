#!/usr/bin/env node

/**
 * Custom Gemini CLI wrapper that runs as a persistent service.
 * It correctly initializes the Gemini client, uses a single chat session
 * to maintain conversation context, and handles tool calls.
 */

import { fileURLToPath, pathToFileURL } from 'url';
import path from 'path';
import readline from 'readline';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Path Configuration ---
const thirdPartyDir = path.resolve(__dirname, '..', '..', 'third_party');
const geminiCliRoot = path.join(thirdPartyDir, 'gemini-cli');
const geminiCliPath = pathToFileURL(geminiCliRoot).toString();
const geminiConfigDir = path.join(thirdPartyDir, '.gemini');

// --- Module Loading ---
let config; // Store the fully initialized config object
let chatSession;

async function initializeChat() {
    try {
        const configLoaderModule = await import(`${geminiCliPath}/dist/src/config/config.js`);
        const loadCliConfig = configLoaderModule.loadCliConfig;

        const settingsPath = path.join(geminiConfigDir, 'settings.json');
        let settings = {};
        if (fs.existsSync(settingsPath)) {
            settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
        }

        if (!settings.tools) {
            settings.tools = {};
        }

        const mockArgv = {
            debug: false, prompt: '', promptInteractive: false, promptWords: [],
            yolo: false, approvalMode: 'default', includeDirectories: [],
            allowedMcpServerNames: [], allowedTools: [], extensions: [],
            experimentalAcp: false, listExtensions: false, screenReader: false,
            allFiles: false, showMemoryUsage: false, checkpointing: false,
            telemetry: false,
        };
        
        process.env.GEMINI_CONFIG_DIR = geminiConfigDir;

        // Load and initialize the config object, then store it globally.
        const loadedConfig = await loadCliConfig(settings, [], `wrapper-session-${Date.now()}`, mockArgv);
        await loadedConfig.initialize();
        await loadedConfig.refreshAuth(settings.selectedAuthType);
        config = loadedConfig; // Store the initialized config

        const client = config.getGeminiClient();
        chatSession = await client.startChat([]);

        return true;
    } catch (error) {
        console.error('[FATAL_ERROR] Error initializing Gemini chat session:', error.message);
        console.error('Full error for debugging:', error);
        process.exit(1);
    }
}

// --- Main Service Logic ---
async function runService() {
    console.log('[DEBUG] Gemini wrapper service started. Initializing chat session...');
    await initializeChat();
    console.log('[DEBUG] Chat session initialized. Waiting for prompts from stdin...');

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false
    });

    rl.on('line', async (line) => {
        const prompt = line.trim();
        if (!prompt) {
            return;
        }

        console.log(`[DEBUG] Sending prompt: ${prompt.substring(0, 80)}...`);

        try {
            const { executeToolCall } = await import(`${geminiCliPath}/node_modules/@google/gemini-cli-core/dist/src/core/nonInteractiveToolExecutor.js`);
            
            let nextMessage = { message: prompt };
            let final_text = '';
            const abortController = new AbortController();

            // Loop to handle multi-turn conversations involving tool calls
            for (let i = 0; i < 5; i++) { // Limit to 5 turns to prevent infinite loops
                const result = await chatSession.sendMessage(nextMessage);
                
                const candidate = result.candidates?.[0];
                if (!candidate || !candidate.content || !candidate.content.parts) {
                    final_text = "[ERROR] Received invalid response from API.";
                    break;
                }

                const parts = candidate.content.parts;
                let hasHandledPart = false;

                // Aggregate text parts
                const textParts = parts.filter(part => typeof part.text === 'string' && !part.thought);
                if (textParts.length > 0) {
                    final_text += textParts.map(part => part.text).join('');
                    hasHandledPart = true;
                }

                // Find and execute a function call
                const functionCallPart = parts.find(part => part.functionCall);
                if (functionCallPart) {
                    
                    const toolResponse = await executeToolCall(config, functionCallPart.functionCall, abortController.signal);
                    
                    nextMessage = {
                        message: {
                            functionResponse: {
                                name: functionCallPart.functionCall.name,
                                response: toolResponse,
                            }
                        }
                    };
                    hasHandledPart = true;
                    continue; // Go to the next iteration to send the tool response
                }

                // If we got here, there are no more tool calls to process.
                break;
            }

            process.stdout.write(final_text);

        } catch (error) {
            console.error(`[ERROR] ${error.message}`);
            process.stdout.write(`[ERROR] An error occurred while processing the prompt.`);
        } finally {
            process.stdout.write('\n[END_RESPONSE]\n');
        }
    });

    rl.on('close', () => {
        console.log('[DEBUG] Stdin stream closed. Exiting wrapper service.');
        process.exit(0);
    });
}

// --- Error Handling & Startup ---
process.on('unhandledRejection', (reason, promise) => {
    console.error('[UNHANDLED_REJECTION]', reason);
    process.exit(1);
});

process.on('uncaughtException', (error) => {
    console.error('[UNCAUGHT_EXCEPTION]', error);
    process.exit(11);
});

runService().catch(error => {
    console.error('[FATAL_ERROR]', error);
    process.exit(1);
});
