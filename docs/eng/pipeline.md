# `Pipeline`

## Overview
The `Pipeline` framework in MiniAutoGen is a flexible and modular system designed for data processing, particularly in chat applications. It allows for the sequential processing of data through a series of [**components**](components.md), each handling specific tasks or transformations.

## Core

### `class Pipeline`
#### Description:
Represents a data processing pipeline, which is a sequence of `PipelineComponent` objects.

#### Attributes:
- `components` (list of `PipelineComponent`): The list of components in the pipeline.

#### Constructor:
##### `__init__(self, components=None)`
- **Purpose**: Initializes the pipeline with a list of components.
- **Parameters**:
  - `components` (list of `PipelineComponent`, optional): The components to be included in the pipeline. Defaults to an empty list if not provided.

#### Methods:
##### `add_component(self, component)`
- **Purpose**: Adds a new component to the pipeline.
- **Parameters**:
  - `component` (`PipelineComponent`): The component to be added.
- **Exceptions**: Raises `TypeError` if the component is not a subclass of `PipelineComponent`.

##### `run(self, state)`
- **Purpose**: Executes the pipeline on the given state, passing the state through each component in sequence.
- **Parameters**:
  - `state` (`ChatPipelineState`): The current state of the chat to be processed.
- **Returns**: The modified `ChatPipelineState` after processing through all components.

## Example Usage

### Creating a Pipeline
```python
my_pipeline = Pipeline(components=[component1, component2])
```

### Adding a Component to the Pipeline
```python
my_pipeline.add_component(new_component)
```