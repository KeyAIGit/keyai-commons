import math, unittest
from dataclasses import replace
from commons_lab.config import ModelConfig
from commons_lab.protocol import Receipt, Round, outer_step

class ConfigTests(unittest.TestCase):
    def test_exact_count(self):self.assertEqual(ModelConfig().parameter_count(),22029696)
    def test_raw_payload(self):self.assertEqual(ModelConfig().parameter_count()*2,44059392)
    def test_invalid_group(self):
        with self.assertRaises(ValueError):replace(ModelConfig(),heads=7).validate()
    def test_invalid_kv(self):
        with self.assertRaises(ValueError):replace(ModelConfig(),kv_heads=4).validate()
    def test_invalid_values(self):
        for kw in ({'layers':0},{'layers':True},{'norm_eps':float('nan')},{'rope_theta':float('inf')},{'context':9000}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):replace(ModelConfig(),**kw).validate()
    def test_hf_shape(self):
        c=ModelConfig().hf_config();self.assertEqual(c['num_key_value_heads'],2)
        self.assertTrue(c['tie_word_embeddings']);self.assertFalse(c['use_cache'])

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.r=Round(1,'parent-hash',2,frozenset(('a','b','c')),2,10.0)
        self.a=Receipt('job1','a',1,'parent-hash',2,(1.,2.))
        self.b=Receipt('job2','b',1,'parent-hash',6,(3.,4.))
    def test_weighted_merge(self):
        self.r.accept(self.a,1);self.r.accept(self.b,2)
        self.assertEqual(self.r.finalize(),((2.5,3.5),8))
    def test_dropout_still_quorum(self):
        self.r.accept(self.a,1);self.r.accept(self.b,2)
        self.assertEqual(len(self.r.accepted),2);self.r.finalize()
    def test_no_quorum_no_commit(self):
        self.r.accept(self.a,1)
        with self.assertRaises(ValueError):self.r.finalize()
        self.assertFalse(self.r.closed)
    def test_retry_idempotent(self):
        self.r.accept(self.a,1);self.assertEqual(self.r.accept(self.a,3),'duplicate')
        self.assertEqual(len(self.r.accepted),1)
    def test_retry_after_commit(self):
        self.r.accept(self.a,1);self.r.accept(self.b,2);self.r.finalize()
        self.assertEqual(self.r.accept(self.a,12),'duplicate')
    def test_conflicting_duplicate(self):
        self.r.accept(self.a,1)
        with self.assertRaises(ValueError):self.r.accept(replace(self.a,tokens=5),2)
    def test_reused_job_different_worker(self):
        self.r.accept(self.a,1)
        with self.assertRaises(ValueError):self.r.accept(replace(self.b,task_id='job1'),2)
    def test_stale_and_parent(self):
        for kw in ({'epoch':0},{'parent':'other'}):
            with self.assertRaises(ValueError):self.r.accept(replace(self.a,**kw),1)
    def test_unknown_worker(self):
        with self.assertRaises(ValueError):self.r.accept(replace(self.a,worker='intruder'),1)
    def test_expired(self):
        with self.assertRaises(ValueError):self.r.accept(self.a,10)
    def test_bad_numeric(self):
        for kw in ({'tokens':0},{'tokens':True},{'tokens':2**32+1},{'delta':(float('nan'),2.)},{'delta':(1.,)},{'delta':(float('inf'),2.)}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):self.r.accept(replace(self.a,**kw),1)
        self.assertEqual(len(self.r.accepted),0)
    def test_no_double_finalize(self):
        self.r.accept(self.a,1);self.r.accept(self.b,2);self.r.finalize()
        with self.assertRaises(ValueError):self.r.finalize()
    def test_finalized_rejects_new(self):
        self.r.accept(self.a,1);self.r.accept(self.b,2);self.r.finalize()
        with self.assertRaises(ValueError):self.r.accept(replace(self.a,task_id='job3',worker='c'),3)
    def test_nesterov_sign(self):
        theta,velocity=outer_step((10.,),(0.,),(2.,),lr=.7,momentum=.9)
        self.assertAlmostEqual(theta[0],7.34);self.assertEqual(velocity,(2.,))
    def test_fedavg_special_case(self):
        self.assertEqual(outer_step((10.,),(0.,),(2.,),lr=1,momentum=0)[0],(8.,))
    def test_optimizer_bad_input(self):
        for args in [((1.,),(0.,),()),((1.,),(0.,),(float('nan'),))]:
            with self.assertRaises(ValueError):outer_step(*args)

class PlanTests(unittest.TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        self.plan=json.loads((Path(__file__).parents[1]/'configs/study.json').read_text())
    def test_missing_data_blocks_execution(self):
        from commons_lab.plan import validate
        r=validate(self.plan);self.assertTrue(r['plan_valid']);self.assertFalse(r['G1_execution_ready'])
        self.assertEqual(r['confirmation_global_steps'],6144)
    def test_wrong_token_count_rejected(self):
        from commons_lab.plan import validate
        self.plan['targets_per_global_step']=1
        with self.assertRaises(ValueError):validate(self.plan)
    def test_public_execution_rejected(self):
        from commons_lab.plan import validate
        self.plan['budgets']['public_training']=True
        with self.assertRaises(ValueError):validate(self.plan)

if __name__=='__main__':unittest.main()
