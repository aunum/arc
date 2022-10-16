![logo](./static/logo.png "Logo")

Arc is a declarative, minimalist, automation-forward machine learning toolkit. It aims to commoditize models by standardizing their IO into a common protocol, making it easy to consume models from _any_ source using your language of choice. [[io.md](./docs/io.md)]   

Arc embraces the multiplicity of models, allowing for the training and inference of many models from any framework in a distributed manor. Arc aims to scale models through a hetergeneous mixture of experts.

Arc makes the machine learning development lifecycle lightweight and ergonomic. Arc models and jobs can easily be shared and reused within a team, company, or the larger world. [[artifacts.md](./docs/artifacts.md)]   

Arc makes use of its standardization patterns to provide rich automation around the selection, tuning, and hardening of models.

-- _Arc is pre-alpha, things can and will break, feel free to open issues and pull requests_ --

## Tenants

* Lightwieght
* Compositional
* Explicit
* Observable
* Cloud native
* Few dependencies
* Easy UX
* Rapid iteration

## Installation

```sh
pip install arcos
```

_Python >= 3.10; Kubernetes >= 1.22.0_

Arc only requires a working `KUBECONFIG` and an image repository (see [artifacts.md](./docs/artifacts.md)). 

Arc has 0 runtime dependencies and works with any vanilla Kubernetes cluster :slightly_smiling_face:  If you need a Kubernetes cluster, Arc works will with [kind](https://kind.sigs.k8s.io/) locally.

Poetry, Conda, and Pip are supported for packaging components.

## Quick Start

See the [MNIST example](examples/mnist/models/keras/classifier.py) for the full example

```python
# Run a local model on Kubernetes, hot reloading code changes
model = ConvMultiClassImageClassifier.develop()

# Run a local job on Kubernetes, which will provide our training data and eval
job = ClassifyDigitsJob.develop()

# Sample one X and Y from the job
sample_img, sample_class = job.sample(1)

# Compile the model to work with the job
model.compile(sample_img, sample_class)

# Stream data from the job and send it to the model to train
for x, y in job.stream():
    metrics = model.fit(x, y)

# Sample from the job and use the trained model to predict
sample_img, sample_class = job.sample(12)
y_pred = model.predict(sample_img)

# Evaluate the trained model on Kubernetes for the job, returning a report
report = job.evaluate(model)
```

More [examples here](./examples)

## Concepts

* [IO](./docs/io.md)
* [Jobs](./docs/jobs.md)
* [Models](./docs/models.md)
* [Trainer](./docs/trainer.md)
* [Artifacts](./docs/artifacts.md)
* [Functions](./docs/functions.md)
* [Finder](./docs/finder.md)
* [Predictor](./docs/predictor.md)

These primitives roughly map to roles:

* Data engineer - Jobs
* Data scientist - Models
* MLE - Trainer, Predictor

## Roadmap

### Core
- [x] Model interface
- [x] Job interface
- [x] Remote model saving
- [x] Trainer interface
- [x] Poetry build environments
- [x] Conda build environments
- [x] Pip build environments
- [ ] Finder interface
- [ ] Predictor interface
- [ ] Router interface
- [ ] Notebook support
- [ ] Whylogs integration:q
- [ ] Kubernetes provider
- [ ] Msgpack encoding
- [ ] Monetization
- [ ] Notebooks on running models as ephemeral containers
- [ ] Actors

### Data types
- [x] Image
- [x] Classes
- [ ] Text
- [ ] Multi-label
- [ ] Video
- [ ] Audio
- [ ] Table
- [ ] Timeseries

### Integrations
- [ ] Huggingface
- [ ] Torch.hub
- [ ] AWS (sagemaker and comprehend)
- [ ] Tensorflow hub
- [ ] Google cloud
- [ ] Replicate

### UX
- [ ] Docs
- [ ] UI
- [ ] Support a second language (Go or JS)
- [ ] CLI
- [ ] Slack Bot

## Contributing

Contributions are welcome, please open an issue