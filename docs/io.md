# X and Y
Much of Arc's capabilities revolve around standardized IO for models and tasks. Arc offers a compositional experience for defining the input and output of models.

Arc provides a set of basic data types for common ML tasks, a user can also implement the [Data class](arc/data/types.py) to extend the functionality to any data type.   

Example types:
```python
X: ImageData | TextData | VideoData | AudioData | TableData
Y: ClassData | LabelData | TextData | ImageData  
```

By defining the common IO types we can now compose them into whatever task we need:

To create a multi-class image classifier we just parameterize the `Model` type with `ImageData` as our `X` and `ClassData` as our `Y`
```python
multi_class_img_classifier = SupervisedModel[ImageData, ClassData]
```

To create a multi-label text classifier we parameterize with `TextData` as our `X` and `LabelData` as our `Y`
```python
multi_label_text_classifier = SupervisedModel[TextData, LabelData]
```

To create a text to image model with parameterize with  `TextData` as our `X` and `ImageData` as our `Y`
```python
txt_to_img_model = SupervisedModel[TextData, ImageData]
```

By standardizing these types we create a highly ergonomic interface which allows us to consistently utilize and evaluate any ML model.