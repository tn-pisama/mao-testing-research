import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';
import Anthropic from '@anthropic-ai/sdk';

export class ClaudeThinking implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Claude (Extended Thinking)',
		name: 'claudeThinking',
		icon: 'file:claude.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Call Claude API with extended thinking capture for PISAMA',
		defaults: {
			name: 'Claude Thinking',
		},
		inputs: ['main'],
		outputs: ['main'],
		credentials: [
			{
				name: 'claudeApi',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Model',
				name: 'model',
				type: 'options',
				default: 'claude-sonnet-4-5-20250514',
				description: 'The Claude model to use',
				options: [
					{
						name: 'Claude Sonnet 4.5',
						value: 'claude-sonnet-4-5-20250514',
					},
					{
						name: 'Claude Opus 4.5',
						value: 'claude-opus-4-5-20251101',
					},
					{
						name: 'Claude Sonnet 3.7',
						value: 'claude-3-7-sonnet-20250219',
					},
					{
						name: 'Claude Haiku 3.5',
						value: 'claude-3-5-haiku-20241022',
					},
				],
			},
			{
				displayName: 'Prompt',
				name: 'prompt',
				type: 'string',
				default: '',
				required: true,
				description: 'The user message/prompt to send to Claude',
				typeOptions: {
					rows: 4,
				},
			},
			{
				displayName: 'System Prompt',
				name: 'systemPrompt',
				type: 'string',
				default: '',
				description: 'Optional system instructions',
				typeOptions: {
					rows: 2,
				},
			},
			{
				displayName: 'Enable Extended Thinking',
				name: 'extendedThinking',
				type: 'boolean',
				default: true,
				description: 'Whether to enable extended thinking mode (captures internal reasoning)',
			},
			{
				displayName: 'Thinking Budget (Tokens)',
				name: 'thinkingBudget',
				type: 'number',
				default: 10000,
				displayOptions: {
					show: {
						extendedThinking: [true],
					},
				},
				description: 'Maximum tokens for thinking (1024-32000)',
				typeOptions: {
					minValue: 1024,
					maxValue: 32000,
				},
			},
			{
				displayName: 'Max Tokens',
				name: 'maxTokens',
				type: 'number',
				default: 4096,
				description: 'Maximum tokens in response',
				typeOptions: {
					minValue: 1,
					maxValue: 8192,
				},
			},
			{
				displayName: 'Temperature',
				name: 'temperature',
				type: 'number',
				default: 1.0,
				description: 'Sampling temperature (0-1)',
				typeOptions: {
					minValue: 0,
					maxValue: 1,
					numberStepSize: 0.1,
				},
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		for (let i = 0; i < items.length; i++) {
			try {
				const credentials = await this.getCredentials('claudeApi', i);
				const apiKey = credentials.apiKey as string;

				const model = this.getNodeParameter('model', i) as string;
				const prompt = this.getNodeParameter('prompt', i) as string;
				const systemPrompt = this.getNodeParameter('systemPrompt', i, '') as string;
				const extendedThinking = this.getNodeParameter('extendedThinking', i, true) as boolean;
				const thinkingBudget = this.getNodeParameter('thinkingBudget', i, 10000) as number;
				const maxTokens = this.getNodeParameter('maxTokens', i, 4096) as number;
				const temperature = this.getNodeParameter('temperature', i, 1.0) as number;

				const anthropic = new Anthropic({ apiKey });

				const requestBody: any = {
					model,
					max_tokens: maxTokens,
					temperature,
					messages: [
						{
							role: 'user',
							content: prompt,
						},
					],
				};

				if (systemPrompt) {
					requestBody.system = systemPrompt;
				}

				// Enable extended thinking if requested
				if (extendedThinking) {
					requestBody.thinking = {
						type: 'enabled',
						budget_tokens: thinkingBudget,
					};
				}

				const startTime = Date.now();
				const response = await anthropic.messages.create(requestBody);
				const endTime = Date.now();

				// Extract thinking and content blocks
				let thinking = '';
				let content = '';

				for (const block of response.content) {
					if (block.type === 'thinking') {
						thinking = block.thinking;
					} else if (block.type === 'text') {
						content = block.text;
					}
				}

				// Structure output for PISAMA ingestion
				const output = {
					json: {
						thinking: thinking || null,
						content,
						model: response.model,
						usage: {
							input_tokens: response.usage.input_tokens,
							output_tokens: response.usage.output_tokens,
						},
						stop_reason: response.stop_reason,
						execution_time_ms: endTime - startTime,
					},
				};

				returnData.push(output);
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: {
							error: error.message,
						},
						pairedItem: { item: i },
					});
					continue;
				}
				throw new NodeOperationError(this.getNode(), error as Error, { itemIndex: i });
			}
		}

		return [returnData];
	}
}
