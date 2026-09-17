"""Offline crash-fault reference. No networking or cryptographic attestation.
These invariants are necessary, not sufficient, for a future distributed service.
"""
from dataclasses import dataclass, field
import math

@dataclass(frozen=True)
class Receipt:
    task_id: str
    worker: str
    epoch: int
    parent: str
    tokens: int
    delta: tuple[float, ...]

@dataclass
class Round:
    epoch: int
    parent: str
    dimension: int
    authorized: frozenset[str]
    quorum: int
    deadline: float
    accepted: dict[str, Receipt] = field(default_factory=dict)
    seen_tasks: set[str] = field(default_factory=set)
    closed: bool = False

    def __post_init__(self):
        if not (type(self.epoch) is int and self.epoch>=0 and self.parent):
            raise ValueError('Invalid round identity')
        if type(self.dimension) is not int or not 0<self.dimension<=10**6:
            raise ValueError('Bounded reference vectors only')
        if not 1<=self.quorum<=len(self.authorized) or not math.isfinite(self.deadline):
            raise ValueError('Invalid quorum/deadline')

    def accept(self, receipt: Receipt, now: float) -> str:
        if not math.isfinite(now):raise ValueError('Invalid clock')
        # Retries acknowledge only an identical, previously committed receipt.
        previous=self.accepted.get(receipt.worker)
        if previous==receipt:return 'duplicate'
        if self.closed or now>=self.deadline:raise ValueError('Round closed or expired')
        if receipt.epoch!=self.epoch or receipt.parent!=self.parent:
            raise ValueError('Wrong base: this stage accepts zero staleness')
        if receipt.worker not in self.authorized or not receipt.task_id:
            raise ValueError('Unknown worker/task')
        if receipt.task_id in self.seen_tasks or previous is not None:
            raise ValueError('Conflicting or reused contribution')
        if type(receipt.tokens) is not int or not 0<receipt.tokens<=2**32:
            raise ValueError('Invalid token count')
        if len(receipt.delta)!=self.dimension or not all(type(x) in (int,float) and math.isfinite(x) for x in receipt.delta):
            raise ValueError('Invalid delta shape or non-finite value')
        self.accepted[receipt.worker]=receipt; self.seen_tasks.add(receipt.task_id)
        return 'accepted'

    def finalize(self):
        if self.closed:raise ValueError('Already finalized')
        if len(self.accepted)<self.quorum:raise ValueError('No quorum; no new checkpoint')
        ordered=[self.accepted[k] for k in sorted(self.accepted)]
        total=sum(r.tokens for r in ordered)
        delta=tuple(math.fsum(r.tokens/total*r.delta[i] for r in ordered) for i in range(self.dimension))
        if not all(math.isfinite(x) for x in delta):raise ValueError('Non-finite aggregate')
        self.closed=True
        return delta,total

def outer_step(theta, velocity, delta, lr=.7, momentum=.9):
    """SGD Nesterov convention matching torch.optim.SGD, dampening=0.
    Delta is (parent - locally_trained), not the opposite sign.
    """
    if not len(theta)==len(velocity)==len(delta) or not theta:raise ValueError('Shape mismatch')
    if not math.isfinite(lr) or lr<=0 or not 0<=momentum<1:raise ValueError('Bad optimizer')
    if not all(math.isfinite(x) for seq in (theta,velocity,delta) for x in seq):raise ValueError('Non-finite optimizer state')
    v=tuple(momentum*v+d for v,d in zip(velocity,delta))
    next_theta=tuple(t-lr*(d+momentum*w) for t,d,w in zip(theta,delta,v))
    if not all(math.isfinite(x) for seq in (v,next_theta) for x in seq):raise ValueError('Overflow')
    return next_theta,v
