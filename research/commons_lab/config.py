"""Pure-stdlib configuration and exact parameter accounting."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class ModelConfig:
    vocab_size: int = 8192
    width: int = 384
    layers: int = 12
    heads: int = 6
    kv_heads: int = 2
    ff_width: int = 1024
    context: int = 512
    rope_theta: float = 10000.0
    norm_eps: float = 1e-6

    def validate(self):
        for k in ('vocab_size','width','layers','heads','kv_heads','ff_width','context'):
            if type(getattr(self,k)) is not int or getattr(self,k) <= 0:
                raise ValueError(f'{k} must be a positive integer')
        if self.width % self.heads or self.heads % self.kv_heads:
            raise ValueError('Head dimensions/groups must divide exactly')
        if (self.width // self.heads) % 2:
            raise ValueError('RoPE requires an even head dimension')
        if not 1 < self.rope_theta < float('inf') or not 0 < self.norm_eps < 1:
            raise ValueError('Invalid normalization or RoPE constants')
        if self.width > 4096 or self.layers > 64 or self.vocab_size > 65536 or self.context > 8192:
            raise ValueError('Config exceeds this research reference envelope')

    def parameter_count(self):
        self.validate()
        w, k = self.width, self.width // self.heads * self.kv_heads
        block = 2*w*w + 2*w*k + 3*w*self.ff_width + 2*w
        return self.vocab_size*w + self.layers*block + w

    def hf_config(self):
        return dict(model_type='llama', architectures=['LlamaForCausalLM'],
                    vocab_size=self.vocab_size,hidden_size=self.width,
                    intermediate_size=self.ff_width,num_hidden_layers=self.layers,
                    num_attention_heads=self.heads,num_key_value_heads=self.kv_heads,
                    max_position_embeddings=self.context,rope_theta=self.rope_theta,
                    rms_norm_eps=self.norm_eps,hidden_act='silu',attention_bias=False,
                    mlp_bias=False,attention_dropout=0.0,tie_word_embeddings=True,
                    initializer_range=0.02,use_cache=False)
