![logo](./static/logo.png "Logo")

Arc is a declarative, minimalist, automation-forward machine learning platform. It aims to commoditize models by standardizing their IO, making it easy to consume models from _any_ source using your language of choice.   

Arc makes the machine learning development lifecycle lightweight and ergonomic. Arc models and jobs can easily be shared and reused within a team, company, or the larger world.   

Arc makes use of its standardization patterns to provide rich automation around the selection, tuning, and hardening of models.

-- _Arc is pre-alpha, things can and will break, feel free to open issues and requests_ --

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
pip install arc-ai
```

Arc only requires a working `KUBECONFIG` and an image repository. Arc has 0 runtime dependencies and works with any vanilla Kubernetes cluster :)    

If you need a kubernetes cluster, Arc works will with [kind](https://kind.sigs.k8s.io/) locally

## Quick Start

See the [MNIST example](examples/mnist/classifier.py) for the full example

```python
# Run a local model on Kubernetes, hot reloading code changes
model = ConvMultiClassImageClassifier.develop()

# Run a local job on kubernetes, which will provid our training data and eval
job = ClassifyDigitsJob.develop()

# Sample one X and Y from the job
sample_img, sample_class = job.sample(1)

# Compile the model to work with the job
model.compile(sample_img, sample_class)

# Stream data from the job and send it to the model to train
for x, y in job.stream():
    metrics = model.fit(x, y)
    print(metrics)


# Sample from the job and use the trained model to predict
sample_img, sample_class = job.sample(12)
y_pred = model.predict(sample_img)

# Evaluate the trained model on Kubernetes for the job, returning a report
report = job.evaluate(model)
```

## Conceptsgi

* [IO](./docs/io.md)
* [Jobs](./docs/jobs.md)
* [Models](./docs/models.md)
* [Trainer](./docs/trainer.md)
* [Finder](./docs/finder.md)
* [Functions](./docs/functions.md)

## Roadmap

### Core
- [x] Remote model saving
- [x] Trainer interface
- [ ] Finder interface
- [ ] Predictor interface
- [ ] Notebook support
- [ ] Conda build environments
- [ ] Pip build environments
- [ ] Whylogs integration
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