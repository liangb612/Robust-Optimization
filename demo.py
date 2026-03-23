import gurobipy as gp
from gurobipy import GRB

"""
双层规划问题：
上层（max）：x + y
下层（min）：x^2 + y^2
约束：x + y >= 1, x >= 0, y >= 0

其中 x 是上层变量，y 是下层变量
"""

# 创建模型
model = gp.Model("bilevel_KKT")

# ========== 定义变量 ==========
# 上层变量 x
x = model.addVar(lb=0, ub=9,name="x")

# 下层变量 y
y = model.addVar(lb=0,ub=9, name="y")

# ========== KKT条件需要的对偶变量 ==========
# 下层问题的KKT条件：
# min (x^2 + y^2) s.t. x + y >= 1
# 等价于 min (x^2 + y^2) s.t. -x - y <= -1
# 拉格朗日函数: L = x^2 + y^2 + λ(-x - y + 1) = x^2 + y^2 - λx - λy + λ
# KKT条件：
# 1. ∂L/∂y = 2y - λ = 0  =>  λ = 2y
# 2. λ ≥ 0
# 3. 互补松弛: λ(-x-y+1) = 0  =>  λ(1-x-y) = 0
# 4. 原始约束: x + y >= 1

lambda_var = model.addVar(lb=0, name="lambda")  # 对偶变量

# 稳定性条件: 2y - lambda = 0
stability = model.addConstr(2 * y - lambda_var == 0, name="stability")

# 原始约束: x + y >= 1
primal_feas = model.addConstr(x + y >= 1, name="primal_feas")

# 互补松弛条件: λ(1-x-y) = 0
# 这个条件可以用分段约束表示：
# λ = 0 或 (1-x-y) = 0
# 即要么 λ = 0，要么 x+y = 1

# 使用辅助二元变量实现互补松弛
z = model.addVar(vtype=GRB.BINARY, name="z")
M1 = 100  # 足够大的数
M2 = 100

# 如果 z = 0，则 λ = 0 (即对偶约束不起作用)
# 如果 z = 1，则 (1-x-y) = 0 (即原约束取等号)
model.addConstr(lambda_var*(1 - x - y) == 0)

# ========== 上层目标（最大化） ==========
model.setObjective(x + y, GRB.MAXIMIZE)

# 设置一些求解参数来提高稳定性
model.Params.NonConvex = 2
model.Params.FeasibilityTol = 1e-6
model.Params.OptimalityTol = 1e-6

# ========== 求解 ==========
try:
    model.optimize()
    
    # ========== 输出结果 ==========
    if model.Status == GRB.OPTIMAL:
        print("\n" + "="*50)
        print("求解成功！")
        print(f"上层目标值: {model.ObjVal:.4f}")
        print(f"x (上层变量): {x.X:.4f}")
        print(f"y (下层变量): {y.X:.4f}")
        print(f"对偶变量 lambda: {lambda_var.X:.4f}")
        print(f"约束 x + y >= 1: {x.X + y.X:.4f} >= 1")
        print("="*50)
        
        # 验证KKT条件
        print("\n验证KKT条件:")
        print(f"稳定性 (2y - λ = 0): {2*y.X - lambda_var.X:.6f}")
        print(f"互补松弛 (λ*(1-x-y) = 0): {lambda_var.X * (1 - x.X - y.X):.6f}")
        print(f"原可行性 (x+y>=1): {x.X + y.X:.4f} >= 1")
        print(f"对偶可行性 (λ>=0): {lambda_var.X:.4f} >= 0")
    else:
        print(f"求解失败，状态码: {model.Status}")
        print("可能的状态码含义：")
        if model.Status == GRB.INFEASIBLE:
            print("- GRB.INFEASIBLE (10): 模型不可行")
        elif model.Status == GRB.UNBOUNDED:
            print("- GRB.UNBOUNDED (11): 模型无界")
        elif model.Status == GRB.INF_OR_UNBD:
            print("- GRB.INF_OR_UNBD (12): 模型不可行或无界")
        else:
            print("- 其他状态，请参考Gurobi文档")
            
except Exception as e:
    print(f"求解过程中出现异常: {e}")