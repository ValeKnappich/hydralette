from hydralette import ConfigBase, config_from_signature, field


def my_func(a: int = 2, b: float = 1):
    return a


class MyClass:
    def __init__(self, c: float = 1.0, d=False):
        pass


class RNN:
    def __init__(self, n_layers: int = 8, dropout: float = 0.1):
        pass


RNNConfig = config_from_signature(RNN)  # <-- generate config class from signature


class Transformer:
    def __init__(self, n_layers: int = 16, grouped_query_attention: bool = False):
        pass


TransformerConfig = config_from_signature(Transformer)


class Config(ConfigBase):
    myclass = field(
        from_signature=MyClass,  # <-- generate config class from signature and use as field
        metadata=dict(help="This is helpful text"),  # <-- all keywords except defaults are passed along
    )
    my_func = field(from_signature=my_func)  # <-- generate config class from signature and use as field
    model = field(  # type: ignore
        default=RNNConfig,
        groups=dict(rnn=RNNConfig, transformer=TransformerConfig),  # <-- generated config classes can also be used in groups
    )


if __name__ == "__main__":
    print("↓ ↓ ↓ ↓ ↓ ↓ ↓ Help Page ↓ ↓ ↓ ↓ ↓ ↓ ↓ \n")
    Config.print_help_page()
    config = Config.create()
    config.print_yaml()
    config.my_func.a
