"""Semantic Kernel integration for MAO tracing.

Microsoft Semantic Kernel is an open-source SDK for building AI agents and
multi-agent systems in C#, Python, and Java.

This integration provides:
- Automatic tracing of kernel function calls
- Plugin invocation monitoring
- Planner execution tracing
- Multi-agent coordination tracking

Usage:
    from semantic_kernel import Kernel
    from mao.integrations import SemanticKernelTracer

    tracer = SemanticKernelTracer(endpoint="http://mao.example.com")
    kernel = Kernel()
    
    # Wrap the kernel for automatic tracing
    traced_kernel = tracer.wrap(kernel)
    
    # Or manually trace specific operations
    with tracer.trace_function("my_plugin", "my_function"):
        result = await kernel.invoke(my_function)
"""

from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from contextlib import asynccontextmanager
import asyncio

from .base import BaseFrameworkTracer, Span


class SemanticKernelTracer(BaseFrameworkTracer):
    """Tracer for Microsoft Semantic Kernel agents."""
    
    FRAMEWORK_NAME = "semantic_kernel"
    FRAMEWORK_VERSION = "1.x"
    
    def __init__(self, endpoint: str = "http://localhost:8000"):
        super().__init__(endpoint)
        self._function_hooks: Dict[str, Callable] = {}
        self._planner_traces: Dict[str, List[str]] = {}
    
    def wrap(self, kernel: Any) -> Any:
        """Wrap a Semantic Kernel instance for automatic tracing.
        
        Args:
            kernel: A semantic_kernel.Kernel instance
            
        Returns:
            The wrapped kernel with tracing enabled
        """
        original_invoke = kernel.invoke
        original_invoke_prompt = getattr(kernel, 'invoke_prompt', None)
        original_invoke_stream = getattr(kernel, 'invoke_stream', None)
        
        tracer = self
        
        async def traced_invoke(function, *args, **kwargs):
            plugin_name = getattr(function, 'plugin_name', 'unknown')
            function_name = getattr(function, 'name', str(function))
            
            span_id = tracer.start_span(
                name=f"sk.invoke.{plugin_name}.{function_name}",
                attributes={
                    "sk.plugin_name": plugin_name,
                    "sk.function_name": function_name,
                    "sk.function_type": "native" if hasattr(function, '__call__') else "semantic",
                    "sk.args": str(args)[:500],
                    "sk.kwargs": str(kwargs)[:500],
                },
            )
            
            try:
                result = await original_invoke(function, *args, **kwargs)
                
                tracer.end_span(
                    span_id,
                    status="OK",
                    attributes={
                        "sk.result_type": type(result).__name__,
                        "sk.result_preview": str(result)[:500] if result else None,
                    },
                )
                return result
                
            except Exception as e:
                tracer.end_span(
                    span_id,
                    status="ERROR",
                    attributes={
                        "error.type": type(e).__name__,
                        "error.message": str(e)[:500],
                    },
                )
                raise
        
        async def traced_invoke_prompt(prompt_template, *args, **kwargs):
            if original_invoke_prompt is None:
                raise NotImplementedError("invoke_prompt not available")
            
            span_id = tracer.start_span(
                name="sk.invoke_prompt",
                attributes={
                    "sk.prompt_template": prompt_template[:500] if prompt_template else None,
                    "sk.kwargs": str(kwargs)[:500],
                },
            )
            
            try:
                result = await original_invoke_prompt(prompt_template, *args, **kwargs)
                tracer.end_span(span_id, status="OK", attributes={
                    "sk.result_preview": str(result)[:500] if result else None,
                })
                return result
            except Exception as e:
                tracer.end_span(span_id, status="ERROR", attributes={
                    "error.type": type(e).__name__,
                    "error.message": str(e)[:500],
                })
                raise
        
        async def traced_invoke_stream(function, *args, **kwargs):
            if original_invoke_stream is None:
                raise NotImplementedError("invoke_stream not available")
            
            plugin_name = getattr(function, 'plugin_name', 'unknown')
            function_name = getattr(function, 'name', str(function))
            
            span_id = tracer.start_span(
                name=f"sk.invoke_stream.{plugin_name}.{function_name}",
                attributes={
                    "sk.plugin_name": plugin_name,
                    "sk.function_name": function_name,
                    "sk.streaming": True,
                },
            )
            
            try:
                chunks = []
                async for chunk in original_invoke_stream(function, *args, **kwargs):
                    chunks.append(str(chunk))
                    yield chunk
                
                tracer.end_span(span_id, status="OK", attributes={
                    "sk.stream_chunks": len(chunks),
                    "sk.result_preview": ''.join(chunks)[:500],
                })
            except Exception as e:
                tracer.end_span(span_id, status="ERROR", attributes={
                    "error.type": type(e).__name__,
                    "error.message": str(e)[:500],
                })
                raise
        
        kernel.invoke = traced_invoke
        if original_invoke_prompt:
            kernel.invoke_prompt = traced_invoke_prompt
        if original_invoke_stream:
            kernel.invoke_stream = traced_invoke_stream
        
        kernel._mao_tracer = self
        return kernel
    
    def extract_agent_info(self, kernel: Any) -> Dict[str, Any]:
        """Extract agent information from a Semantic Kernel instance."""
        plugins = {}
        
        if hasattr(kernel, 'plugins'):
            for plugin_name, plugin in kernel.plugins.items():
                functions = []
                if hasattr(plugin, 'functions'):
                    for func_name, func in plugin.functions.items():
                        functions.append({
                            "name": func_name,
                            "description": getattr(func, 'description', None),
                            "is_semantic": hasattr(func, 'prompt_template'),
                        })
                plugins[plugin_name] = {
                    "name": plugin_name,
                    "functions": functions,
                }
        
        return {
            "framework": self.FRAMEWORK_NAME,
            "framework_version": self.FRAMEWORK_VERSION,
            "plugins": plugins,
            "services": list(kernel.services.keys()) if hasattr(kernel, 'services') else [],
        }
    
    @asynccontextmanager
    async def trace_function(self, plugin_name: str, function_name: str):
        """Context manager for manually tracing function calls.
        
        Usage:
            async with tracer.trace_function("my_plugin", "my_function"):
                result = await do_something()
        """
        span_id = self.start_span(
            name=f"sk.manual.{plugin_name}.{function_name}",
            attributes={
                "sk.plugin_name": plugin_name,
                "sk.function_name": function_name,
                "sk.manual_trace": True,
            },
        )
        
        try:
            yield span_id
            self.end_span(span_id, status="OK")
        except Exception as e:
            self.end_span(span_id, status="ERROR", attributes={
                "error.type": type(e).__name__,
                "error.message": str(e)[:500],
            })
            raise
    
    def trace_planner(self, planner: Any) -> Any:
        """Wrap a Semantic Kernel planner for tracing.
        
        Supports:
        - SequentialPlanner
        - StepwisePlanner
        - ActionPlanner
        - HandlebarsPlanner
        """
        original_create_plan = planner.create_plan
        tracer = self
        
        async def traced_create_plan(goal: str, *args, **kwargs):
            span_id = tracer.start_span(
                name=f"sk.planner.{type(planner).__name__}",
                attributes={
                    "sk.planner_type": type(planner).__name__,
                    "sk.goal": goal[:500],
                },
            )
            
            try:
                plan = await original_create_plan(goal, *args, **kwargs)
                
                steps = []
                if hasattr(plan, 'steps'):
                    steps = [str(s) for s in plan.steps]
                elif hasattr(plan, '_steps'):
                    steps = [str(s) for s in plan._steps]
                
                tracer.end_span(span_id, status="OK", attributes={
                    "sk.plan_steps": len(steps),
                    "sk.plan_preview": str(steps)[:500],
                })
                
                tracer._planner_traces[span_id] = steps
                return plan
                
            except Exception as e:
                tracer.end_span(span_id, status="ERROR", attributes={
                    "error.type": type(e).__name__,
                    "error.message": str(e)[:500],
                })
                raise
        
        planner.create_plan = traced_create_plan
        planner._mao_tracer = self
        return planner
    
    def trace_chat_completion(self, chat_service: Any) -> Any:
        """Wrap a chat completion service for tracing."""
        original_complete = chat_service.complete_chat
        tracer = self
        
        async def traced_complete(messages: List[Any], *args, **kwargs):
            span_id = tracer.start_span(
                name="sk.chat_completion",
                attributes={
                    "sk.message_count": len(messages),
                    "sk.model": getattr(chat_service, 'model_id', 'unknown'),
                    "sk.service_type": type(chat_service).__name__,
                },
            )
            
            try:
                result = await original_complete(messages, *args, **kwargs)
                
                tracer.end_span(span_id, status="OK", attributes={
                    "sk.response_preview": str(result)[:500] if result else None,
                    "sk.usage": getattr(result, 'usage', None),
                })
                return result
                
            except Exception as e:
                tracer.end_span(span_id, status="ERROR", attributes={
                    "error.type": type(e).__name__,
                    "error.message": str(e)[:500],
                })
                raise
        
        chat_service.complete_chat = traced_complete
        return chat_service


def create_semantic_kernel_tracer(
    endpoint: str = "http://localhost:8000",
    auto_instrument: bool = True,
) -> SemanticKernelTracer:
    """Factory function to create a Semantic Kernel tracer.
    
    Args:
        endpoint: MAO backend endpoint
        auto_instrument: If True, automatically instrument imported Kernel classes
        
    Returns:
        Configured SemanticKernelTracer instance
    """
    tracer = SemanticKernelTracer(endpoint=endpoint)
    
    if auto_instrument:
        try:
            import semantic_kernel
            original_kernel_init = semantic_kernel.Kernel.__init__
            
            def patched_init(self, *args, **kwargs):
                original_kernel_init(self, *args, **kwargs)
                tracer.wrap(self)
            
            semantic_kernel.Kernel.__init__ = patched_init
        except ImportError:
            pass
    
    return tracer
