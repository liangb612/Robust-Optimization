import gurobipy as gp
import numpy as np
from gurobipy import GRB

def mainProblem_iterate_min(model1:gp.Model,uout:dict):
  #打印输入的值
  print(uout)
  '''
  已知参数
  '''
  alpha = 0.9
  w_l = np.array([0.9, 1, 1.1])
  pw_f = np.array(
    [188,237,188,181,204,156,174,186,118,
                    89,77,54,52,80,82,107,144,185,163,221,215,
                    240,223,190,]
                  ).reshape(1,24)
  pv_f = 10*np.array(
          [0,0,0,0,0,2.2000,5.5000,17.0000,28.6000,32.0000,39.0000,42.6000,42.0000,
            41.6000,40.5000,41.2000,36.5000,28.0000,16.0000,6.6000,1.1000,0,
            0,0,]
                ).reshape(1,24)
  pload = 0.5*np.array(
          [945,845,745,780,998,1095,1147,1199,1300,1397,1449,1498,1397,1297,
          1197,1048,1000,1100,1202,1375,1298,1101,900,800,]
                  )#双峰负荷曲线
  p_g_min = np.array([200, 200, 150, 120, 70])
  p_g_max = np.array([460, 400, 350, 300, 150])
  p_h_max = 280
  remp_u_d = np.array([240, 210, 150, 120, 70])  # >=pgmin
  t_on_and_off = np.array([8, 7, 6, 4, 3])
  a = 1e-5 * np.array([1.02, 1.21, 2.17, 3.42, 6.63])
  b = np.array([0.277, 0.288, 0.29, 0.292, 0.306])
  c = np.array([9.2, 8.8, 7.2, 5.2, 3.5])
  sit = np.array([25.6, 22.3, 16.2, 12.3, 4.6])
  e = np.array([0.877, 0.877, 0.877, 0.877, 0.979])
  lamda = np.array([0.94, 0.94, 0.94, 0.94, 1.03])
  # 储能模型中的常量
  capmax = 400
  p_s_max = 100
  p_s_min= 0
  socmax = 0.9#储能电量百分比
  socmin = 0.2
  theta = 0.01
  yita = 0.95
  kees = 0.009
  # 碳交易
  w = 50
  d = 100
  tao = 0.25
  #碳排放因子
  #___________
  # 循环控制变量
  # 时间
  T = 24
  # 火力发电机组数
  n_g = 5

  '''
  约束规划
  '''
  #火电变量
  p_g = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,name="火电出力")
  p_g_2 = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,name = "火电出力的平方线性化")
  u_g = uout["ug"]
  u_start = uout["ustart"]
  u_stop = uout["ustop"]
  #火电约束
  #上下限约束，个数ng x T，爬坡约束，个数ng x T
  model1.addConstrs((p_g[i,j]<=u_g[i,j]*p_g_max[i] for i in range(n_g) for j in range(T)))
  model1.addConstrs((p_g[i,j]>=u_g[i,j]*p_g_min[i] for i in range(n_g) for j in range(T)))
  for i in range(n_g):
    for t in range(T):
      if(t==0):
        model1.addConstr(p_g[i,t]<=remp_u_d[i])#初值设为0
      else:  
        model1.addConstr(p_g[i,t]-p_g[i,t-1]<=remp_u_d[i])
        model1.addConstr(p_g[i,t-1]-p_g[i,t]<=remp_u_d[i])

  '''
  for i in range(n_g):
    for t in range(T):

      if t==0:
        model1.addConstr(u_start[i,t]-u_stop[i,t] == u_g[i,t])
      else:
        model1.addConstr(u_start[i,t]-u_stop[i,t] == u_g[i,t]-u_g[i,t-1])
      model1.addConstr(u_start[i,t] + u_stop[i,t] <=1)
      for k in range(t_on_and_off[i]):
        model1.addConstr(u_start[i,t]<=u_g[i,min(t+k,T-1)])
        model1.addConstr(u_stop[i,t]<=1-u_g[i,min(t+k,T-1)])
        '''
  #火电成本
  #线性化二次项
  lxpg2=np.array([np.linspace(start =0,stop=p_g_max[i],num=11) for i in range(n_g)])
  lypg2 = lxpg2**2
  for n in range(n_g):
    for t in range(T):
      model1.addGenConstrPWL(p_g[n, t].item(), p_g_2[n, t].item(), lxpg2[n],lypg2[n])
  c_g = 0
  c_u = 0
  for i in range(n_g):
    for t in range(T):
      c_gi = a[i]*p_g_2[i,t]+ b[i]*p_g[i,t]+ c[i]
      c_u =c_u+ sit[i]*(u_start[i,t]+u_stop[i,t])
      c_g +=c_gi

  #水电：
  #变量：
  p_h = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name = "水电出力")
  # 约束：
  model1.addConstr(p_h<=p_h_max)
  # 成本：无
  
  #储能：
  soc0 = 0.5
  # 变量：
  soc = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = socmin,ub = socmax,name = "电量百分比")
  p_ch = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="储能充电功率")
  p_dis = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="储能放电功率")
  u_ch = uout["uch"]
  u_dis = uout["udis"]
#约束：
  model1.addConstr(p_ch<=p_s_max*u_ch)
  model1.addConstr(p_dis<=p_s_max*u_dis)
  model1.addConstr(soc[0,0] == soc0*(1-theta)+u_ch[0,0]*yita*p_ch[0,0]/capmax-u_dis[0,0]/yita*p_dis[0,0]/capmax)
  for t in range(1,T):
    model1.addConstr(soc[0,t] == soc[0,t-1]*(1-theta)+u_ch[0,t]*p_ch[0,t]*yita/capmax-u_dis[0,t]*p_dis[0,t]/yita/capmax)
  #model1.addConstr(u_ch+u_dis<=1)
  #model1.addConstr(u_ch+u_dis>=0)
  model1.addConstr(soc[0,23]==soc0)
  #成本：维护成本
  c_ees = kees*gp.quicksum(p_ch[0,t].item()*yita+p_dis[0,t].item()/yita for t in range(T))
  
  #风光电：
  F = 12#保守性调节常量
  d_p_w_max = 0.1#箱式边界系数
  d_p_v_max = 0.1
  #变量：
  p_w = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = 0,name="风电出力")
  p_v = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = 0,name="光电出力")
  u_w = model1.addMVar((1,T),vtype=GRB.BINARY,name="风电运行状态")
  u_v = model1.addMVar((1,T),vtype=GRB.BINARY,name="光电运行状态")
  #约束：
  model1.addConstr(gp.quicksum(u_w[0,t].item() for t in range(T))<=F)
  model1.addConstr(gp.quicksum(u_v[0,t].item() for t in range(T))<=F)
  model1.addConstr(p_w == pw_f-u_w*d_p_w_max*pw_f)#箱式边界的下界
  model1.addConstr(p_v == pv_f-u_v*d_p_v_max*pv_f)
  #成本:主要是弃风光惩罚
  c_wvt = 500*(pw_f-p_w)+500*(pv_f-p_v)
  c_wv=0
  for t in range(T):
    c_wv +=c_wvt[0,t]

  #负载模糊清晰化
  p_l_b = ((1 - alpha) * w_l[0] / 2+ w_l[1] / 2+ w_l[2] * alpha / 2) * pload
  print(f"plb:{p_l_b}")

  #电网：
  p_g_i=model1.addMVar((1, 24), lb=0,vtype=GRB.CONTINUOUS)
  pgmaxsum=model1.addMVar((1, 24),lb=0 ,vtype=GRB.CONTINUOUS)
  # 约束：
  for t in range(24):
      p_g_i_temp = gp.quicksum(p_g[n, t].item() for n in range(n_g))
      model1.addConstr(p_g_i[0,t]== p_g_i_temp)
  model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-p_g_i==0)

  for t in range(24):
      pgmaxsum_temp = gp.quicksum(u_g[n, t].item() * p_g_max[n] for n in range(n_g))
      model1.addConstr(pgmaxsum[0,t] == pgmaxsum_temp)
  model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-pgmaxsum<=0)
  
#使用KKT条件转化为max：乘子始终对应“≤ 0”形式的约束，且非负。
#火电对偶变量
  dl_p_g_max = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="功率上限对偶变量")
  dl_p_g_min = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="功率下限限对偶变量")
  dl_remp_g_max = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="爬坡约束对偶变量")
  dl_remp_g_min = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="爬坡下限对偶变量")
#功率平衡约束对偶变量  
  dl_peq = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,name="功率平衡约束对偶变量")
  dl_prot = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="旋转备用约束对偶变量")
  #水电约束对偶变量：
  dl_ph_max= model1.addMVar(shape = (1,T),vtype=GRB.CONTINUOUS,lb=0,name="水电上限对偶")
  dl_ph_min= model1.addMVar(shape = (1,T),vtype=GRB.CONTINUOUS,lb=0,name="水电下限对偶")
  
  #对偶可行性，不等式约束下限为零，等式约束不限制
  
  #互补松弛 对偶变量与原来的约束只有一个取到等号，不等式约束为取到等号的时候，其对偶变量必然不为0，
  #对偶变量为零时，约束必然不取等号，或者两个都取到等号
  #火电互补松弛：
  model1.addConstrs(((p_g[i,j]-u_g[i,j]*p_g_max[i])*dl_p_g_max[i,j]==0 for i in range(n_g) for j in range(T)))
  model1.addConstrs(((-p_g[i,j]+u_g[i,j]*p_g_min[i])*dl_p_g_min[i,j]==0 for i in range(n_g) for j in range(T)))
  for i in range(n_g):
    for t in range(T):
      if(t==0):
        model1.addConstr((p_g[i,t]-remp_u_d[i])*dl_remp_g_max[i,t]==0)#初值设为0
      else:  
        model1.addConstr((p_g[i,t]-p_g[i,t-1]-remp_u_d[i])*dl_remp_g_max[i,t]==0)
        model1.addConstr((p_g[i,t-1]-p_g[i,t]-remp_u_d[i])*dl_remp_g_min[i,t]==0)
  
  #水电互补松弛：
  model1.addConstr((p_h-p_h_max)*dl_ph_max==0)
  model1.addConstr(-p_h*dl_ph_min==0)
  #平稳性 拉格朗日函数为所有目标函数+对偶变量乘以约束，拉格朗日函数对原始优化变量的导数为0
  #火电平稳性：求出拉格朗日函数，对每个变量求偏导，结果相加等于0
  for i in range(n_g):
    for t in range(T):
      if t==0:
        D_lagrange_p_g = a[i]*p_g[i,t]+b[i]+dl_p_g_max[i,t]-dl_p_g_min[i,t]+dl_remp_g_max[i,t]-dl_remp_g_max[i,t+1]+dl_p_g_min[i,t+1]-dl_peq[0,t] 
      elif t==23:
        D_lagrange_p_g = a[i]*p_g[i,t]+b[i]+dl_p_g_max[i,t]-dl_p_g_min[i,t]+dl_remp_g_max[i,t]-dl_p_g_min[i,t]-dl_peq[0,t] 
      else:
        D_lagrange_p_g = a[i]*p_g[i,t]+b[i]+dl_p_g_max[i,t]-dl_p_g_min[i,t]+dl_remp_g_max[i,t]-dl_remp_g_max[i,t+1]-dl_remp_g_min[i,t]+dl_remp_g_min[i,t+1]-dl_peq[0,t]
      model1.addConstr(D_lagrange_p_g==0)  
  #水电平稳性：
  model1.addConstr(dl_ph_max-dl_ph_min-dl_prot-dl_peq==0)
  #储能
  #储能对偶变量：
  #储能SOC约束为初始时刻、23个递推约束、初末状态相等约束总共25个
  dl_soc = model1.addMVar((1,25),vtype=GRB.CONTINUOUS,name= "储能soc约束对偶变量")
  dl_p_ch_max = model1.addMVar(shape=(1,24),vtype=GRB.CONTINUOUS,lb=0,name="充电功率上限对偶")
  dl_p_ch_min= model1.addMVar(shape=(1,24),vtype=GRB.CONTINUOUS,lb=0,name = "充电功率下限对偶")
  dl_p_dis_max = model1.addMVar(shape=(1,24),vtype=GRB.CONTINUOUS,lb=0,name="放电功率上限对偶")
  dl_p_dis_min= model1.addMVar(shape=(1,24),vtype=GRB.CONTINUOUS,lb=0,name = "放电功率下限对偶")
  #储能互补松弛：
  model1.addConstr((p_ch-p_s_max*u_ch)*dl_p_ch_max==0)
  model1.addConstr((p_dis-p_s_max*u_dis)*dl_p_dis_max==0)
  #等式约束无互补松弛，
  #model1.addConstr(soc[0,0] == soc0*(1-theta)+u_ch[0,0]*yita*p_ch[0,0]/capmax-u_dis[0,0]/yita*p_dis[0,0]/capmax)
  #for t in range(1,T):
   # model1.addConstr(soc[0,t] == soc[0,t-1]*(1-theta)+u_ch[0,t]*p_ch[0,t]*yita/capmax-u_dis[0,t]*p_dis[0,t]/yita/capmax)
  #model1.addConstr(u_ch+u_dis<=1)
  #model1.addConstr(u_ch+u_dis>=0)
  #model1.addConstr(soc[0,23]==soc0)
  model1.addConstr(-p_ch*dl_p_ch_min==0)
  model1.addConstr(-p_dis*dl_p_dis_min==0)
  #储能平稳性
  
  for t in range(1,T):
    if t==0:
      model1.addConstr(dl_soc[0,0]-dl_soc[0,t+1]*(1-theta)==0)
    elif t==23:
      model1.addConstr(dl_soc[0,t]+dl_soc[0,24]==0)
    else:
      model1.addConstr(dl_soc[0,t]-dl_soc[0,t+1]*(1-theta)==0)
  for t in range(T):
    model1.addConstr(dl_p_ch_max[0,t]-dl_p_ch_min[0,t]+kees*yita-u_ch[0,t]*yita/capmax*dl_soc[0,t]+dl_peq[0,t]+dl_prot[0,t]==0)
    model1.addConstr(dl_p_dis_max[0,t]-dl_p_dis_min[0,t]+kees/yita + u_dis[0,t]/yita/capmax*dl_soc[0,t] - dl_peq[0,t]-dl_prot[0,t]==0)
  #电网KKT：
  model1.addConstr((p_l_b+p_ch-p_dis-p_w-p_v-p_h-pgmaxsum)*dl_prot==0)

  #目标函数加入KKT条件后失效，直接并入外层的max 
  
  '''
  ------------------------------------------------------------------
  '''
  C = model1.addVar(1,vtype=GRB.CONTINUOUS,name="子问题最恶劣场景下的成本")
  model1.addConstr( C <= c_g+c_ees)
  '''
  -------------------------------------------------------------------
  '''
  model1.Params.NonConvex = 2
  model1.setObjective(C+c_wv, GRB.MAXIMIZE)
  model1.optimize()
  if model1.status != GRB.OPTIMAL:
      print("Model is infeasible. Computing IIS...")
      model1.computeIIS()
      model1.write("infeasible.ilp")
      print("IIS written to 'infeasible.ilp'")
  elif model1.status == GRB.UNBOUNDED:
      print("IIS written to 'infeasible.ilp un'")
  else:
    LBin = model1.ObjVal
    P_G = p_g.X
    P_W = p_w.X
    P_CH = p_ch.X
    P_DIS = p_dis.X
    P_H = p_h.X
    P_V = p_v.X
    soc = soc.X
    U_V=u_v.X
    U_W =u_w.X 
    rst = {
      "P_G": P_G,
      "P_W": P_W,
      "P_CH": P_CH,
      "P_DIS": P_DIS,
      "P_H": P_H,
      "P_V": P_V,
      "SOC": soc,
      "LBin": LBin,
      "U_V":U_V,
      "U_W":U_W
    }

    return(rst)
